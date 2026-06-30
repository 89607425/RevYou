"""Orchestrator: builds and runs multi-agent review graphs (FAST parallel / DEBATE serial)."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import TypedDict, Annotated

def _merge_dicts(a: dict, b: dict) -> dict:
    return {**a, **b}

from langgraph.graph import StateGraph, END

from app.agents.pm_agent import PMAgent
from app.agents.dev_agent import DevAgent
from app.agents.qa_agent import QAAgent
from app.agents.tools import tool_registry

logger = logging.getLogger(__name__)

AGENT_MODEL_KEY_MAP = {
    "PM_REVIEW": "pm_model",
    "DEV_REVIEW": "dev_model",
    "QA_REVIEW": "qa_model",
}

AGENT_LABELS = {
    "PM_REVIEW": "PM (产品视角)",
    "DEV_REVIEW": "Dev (技术视角)",
    "QA_REVIEW": "QA (测试视角)",
}

CROSS_REVIEW_PROMPT = """你是一位{role}，请审查以下由{source_role}发现的问题。对每个问题判断是否同意，并可以补充意见。

审查的问题：
{issues_json}

请对每个问题输出你的判断：
```json
{{
  "tags": [
    {{
      "issue_index": 0,
      "tag": "CONFIRMED",
      "comment": "同意这个问题的判断"
    }},
    {{
      "issue_index": 1,
      "tag": "QUESTIONED",
      "comment": "质疑理由..."
    }},
    {{
      "issue_index": 2,
      "tag": "SUPPLEMENTED",
      "comment": "补充的具体意见..."
    }}
  ]
}}
```

tag取值：CONFIRMED（同意）/ QUESTIONED（质疑）/ SUPPLEMENTED（补充）
"""


class ReviewMode(str, Enum):
    FAST = "DETERMINISTIC"
    DEBATE = "DEBATE"


class ReviewState(TypedDict):
    session_id: str
    project_id: str
    prd_content: str
    prd_structure: dict
    prd_images: list
    agent_mode: str
    project_config: dict

    issues: Annotated[list, lambda a, b: a + b]
    follow_ups: Annotated[list, lambda a, b: a + b]
    agent_statuses: Annotated[dict, _merge_dicts]
    current_round: int

    pending_follow_ups: list
    user_answers: list

    pm_issues: list
    dev_issues: list
    qa_issues: list
    cross_review_tags: Annotated[list, lambda a, b: a + b]

    final_issues: list
    session_status: str


def _resolve_agent_model(agent_name: str, config: dict) -> str:
    key = AGENT_MODEL_KEY_MAP.get(agent_name, "text_model")
    return config.get(key, config.get("text_model", "deepseek-v3"))


async def _send_progress(ws, session_id: str, agent_name: str, phase: str, message: str):
    if not ws or not session_id:
        return
    try:
        label = AGENT_LABELS.get(agent_name, agent_name)
        await ws.send_message(session_id, "AGENT_THINKING", {
            "agent": agent_name,
            "message": f"{label} {message}",
            "phase": phase,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


class DebateOrchestrator:
    """Orchestrates multi-agent review with FAST (parallel) or DEBATE (serial cross-review) modes."""

    def __init__(self, project_config: dict, ws_manager=None):
        self.config = project_config
        self.ws = ws_manager
        self._pm_agent: PMAgent | None = None
        self._dev_agent: DevAgent | None = None
        self._qa_agent: QAAgent | None = None

    def _init_agents(self, state: ReviewState):
        from app.agents.builtin_tools import register_tapd_tools, register_doc_tools, register_db_tools
        from app.agents.tools import tool_registry

        register_tapd_tools()
        register_doc_tools()
        register_db_tools()

        pm_model = _resolve_agent_model("PM_REVIEW", self.config)
        dev_model = _resolve_agent_model("DEV_REVIEW", self.config)
        qa_model = _resolve_agent_model("QA_REVIEW", self.config)

        has_images = any(
            img.get("recognition_status") == "COMPLETED"
            for img in state.get("prd_images", [])
        )
        if has_images and self.config.get("auto_switch_model", True):
            mm = self.config.get("multimodal_model", "glm-4v-plus")
            pm_model = dev_model = qa_model = mm

        prd = state.get("prd_content", "")
        pid = state.get("project_id", "")
        token = self.config.get("tapd_token", "")
        story_ws = self.config.get("tapd_workspace_id", "")
        bug_ws = self.config.get("tapd_bug_workspace_id", "")

        base_ctx = {"prd_content": prd, "project_id": pid, "api_token": token, "tapd_workspace_id": story_ws, "tapd_bug_workspace_id": bug_ws}

        self._pm_agent = PMAgent(
            model=pm_model,
            tools=tool_registry.get_by_category("tapd") + tool_registry.get_by_category("tapd_bug") + tool_registry.get_by_category("document"),
        )
        self._pm_agent.set_context(base_ctx)

        self._dev_agent = DevAgent(
            model=dev_model,
            tools=tool_registry.get_by_category("tapd_bug") + tool_registry.get_by_category("document") + tool_registry.get_by_category("database"),
        )
        self._dev_agent.set_context(base_ctx)

        self._qa_agent = QAAgent(
            model=qa_model,
            tools=tool_registry.get_by_category("tapd_bug") + tool_registry.get_by_category("database"),
        )
        self._qa_agent.set_context(base_ctx)

    def _get_agent(self, name: str):
        return {"PM_REVIEW": self._pm_agent, "DEV_REVIEW": self._dev_agent, "QA_REVIEW": self._qa_agent}[name]

    def _get_parse_response_fn(self, agent_name: str):
        from app.services.agent_engine import parse_agent_response, extract_follow_ups_from_response
        return parse_agent_response, extract_follow_ups_from_response

    async def _run_agent(
        self, state: ReviewState, agent_name: str, extra_context: str = ""
    ) -> dict:
        agent = self._get_agent(agent_name)
        session_id = state.get("session_id", "")
        parse_fn, extract_fu_fn = self._get_parse_response_fn(agent_name)

        await _send_progress(self.ws, session_id, agent_name, "STARTING", "开始审查...")

        user_content = f"请审查以下PRD文档：\n\n{state['prd_content'][:30000]}"
        if extra_context:
            user_content += f"\n\n{extra_context}"
        if state.get("user_answers"):
            user_content += "\n\n## 用户补充信息\n"
            for ans in state["user_answers"]:
                user_content += f"- {ans.get('answer', '')}\n"

        await _send_progress(self.ws, session_id, agent_name, "READING",
                             f"正在阅读PRD文档（{len(state['prd_content'])} 字符）...")

        if agent.supports_function_calling and agent.tools:
            await _send_progress(self.ws, session_id, agent_name, "THINKING", "正在使用工具调用进行分析...")
        else:
            await _send_progress(self.ws, session_id, agent_name, "THINKING", "正在调用 LLM 进行分析...")

        try:
            raw_response = await asyncio.wait_for(
                agent.run(user_content, timeout=120.0),
                timeout=120.0,
            )
        except asyncio.TimeoutError:
            await _send_progress(self.ws, session_id, agent_name, "TIMEOUT", "审查超时（120秒）")
            return {
                "issues": [{
                    "title": f"[{agent_name}] 审查超时", "issue_type": "LOGIC_GAP",
                    "severity": "LOW", "description": "Agent审查超时",
                    "suggestion": "请重试", "confidence": 0.3,
                }],
                "follow_ups": [],
            }

        await _send_progress(self.ws, session_id, agent_name, "PARSING", "LLM 响应已返回，正在解析结果...")

        issues = parse_fn(raw_response, agent_name)
        for issue in issues:
            issue["source_agent"] = agent_name

        follow_ups = []
        if state["agent_mode"] == "AUTONOMOUS":
            follow_ups = extract_fu_fn(raw_response)[:5]

        await _send_progress(self.ws, session_id, agent_name, "COMPLETED",
                             f"审查完成，发现 {len(issues)} 个问题")

        return {"issues": issues, "follow_ups": follow_ups}

    # ─── Nodes ───

    async def parse_prd_node(self, state: ReviewState) -> dict:
        prd_images = state.get("prd_images", [])
        from app.services.agent_engine import call_multimodal_model
        for img in prd_images:
            if img.get("recognition_status") == "PENDING" and img.get("local_path"):
                try:
                    mm = self.config.get("multimodal_model", "glm-4v-plus")
                    result = await call_multimodal_model(
                        img["local_path"],
                        "请描述这张图片的内容，重点关注：流程步骤、状态转换、数据流向、关键节点。以结构化文本输出。",
                        model=mm,
                    )
                    if result:
                        img["recognition_status"] = "COMPLETED"
                        img["recognition_result"] = result
                except Exception:
                    img["recognition_status"] = "FAILED"

        from app.services.prd_parser import enrich_prd_with_image_text
        enriched = enrich_prd_with_image_text(state["prd_content"], prd_images)

        self._init_agents(state)

        return {
            "prd_content": enriched,
            "prd_images": prd_images,
            "agent_statuses": {"PM_REVIEW": "PENDING", "DEV_REVIEW": "PENDING", "QA_REVIEW": "PENDING"},
            "issues": [],
            "follow_ups": [],
            "pm_issues": [],
            "dev_issues": [],
            "qa_issues": [],
            "cross_review_tags": [],
            "current_round": 1,
            "pending_follow_ups": [],
            "user_answers": [],
        }

    async def pm_fast_node(self, state: ReviewState) -> dict:
        result = await self._run_agent(state, "PM_REVIEW")
        return {
            "issues": result["issues"],
            "follow_ups": result.get("follow_ups", []),
            "agent_statuses": {"PM_REVIEW": "COMPLETED"},
        }

    async def dev_fast_node(self, state: ReviewState) -> dict:
        result = await self._run_agent(state, "DEV_REVIEW")
        return {
            "issues": result["issues"],
            "follow_ups": result.get("follow_ups", []),
            "agent_statuses": {"DEV_REVIEW": "COMPLETED"},
        }

    async def qa_fast_node(self, state: ReviewState) -> dict:
        result = await self._run_agent(state, "QA_REVIEW")
        return {
            "issues": result["issues"],
            "follow_ups": result.get("follow_ups", []),
            "agent_statuses": {"QA_REVIEW": "COMPLETED"},
        }

    async def pm_debate_node(self, state: ReviewState) -> dict:
        result = await self._run_agent(state, "PM_REVIEW")
        return {
            "issues": result["issues"],
            "follow_ups": result.get("follow_ups", []),
            "agent_statuses": {"PM_REVIEW": "COMPLETED"},
            "pm_issues": result["issues"],
        }

    async def dev_debate_node(self, state: ReviewState) -> dict:
        pm_issues = state.get("pm_issues", [])
        ctx = ""
        if pm_issues:
            ctx = "## PM 已发现的以下问题，请基于此进行交叉审查：\n"
            for i, iss in enumerate(pm_issues[:15]):
                ctx += f"{i+1}. [{iss.get('severity','?')}] {iss.get('title','')}: {iss.get('description','')[:200]}\n"
        result = await self._run_agent(state, "DEV_REVIEW", extra_context=ctx)
        return {
            "issues": result["issues"],
            "follow_ups": result.get("follow_ups", []),
            "agent_statuses": {"DEV_REVIEW": "COMPLETED"},
            "dev_issues": result["issues"],
        }

    async def qa_debate_node(self, state: ReviewState) -> dict:
        pm_issues = state.get("pm_issues", [])
        dev_issues = state.get("dev_issues", [])
        ctx = "## 前序 Agent 已发现的问题，请基于此进行交叉审查：\n"
        if pm_issues:
            ctx += "\n### PM 发现的问题：\n"
            for i, iss in enumerate(pm_issues[:10]):
                ctx += f"{i+1}. [{iss.get('severity','?')}] {iss.get('title','')}: {iss.get('description','')[:150]}\n"
        if dev_issues:
            ctx += "\n### Dev 发现的问题：\n"
            for i, iss in enumerate(dev_issues[:10]):
                ctx += f"{i+1}. [{iss.get('severity','?')}] {iss.get('title','')}: {iss.get('description','')[:150]}\n"
        result = await self._run_agent(state, "QA_REVIEW", extra_context=ctx)
        return {
            "issues": result["issues"],
            "follow_ups": result.get("follow_ups", []),
            "agent_statuses": {"QA_REVIEW": "COMPLETED"},
            "qa_issues": result["issues"],
        }

    async def cross_review_node(self, state: ReviewState) -> dict:
        """Have each agent review the OTHER agents' issues and tag them."""
        pm_issues = state.get("pm_issues", [])
        dev_issues = state.get("dev_issues", [])
        qa_issues = state.get("qa_issues", [])

        cross_tags = []

        cross_pairs = [
            ("PM_REVIEW", pm_issues, "DEV_REVIEW", dev_issues, "从技术视角审查 PM 发现的问题"),
            ("PM_REVIEW", pm_issues, "QA_REVIEW", qa_issues, "从测试视角审查 PM 发现的问题"),
            ("DEV_REVIEW", dev_issues, "PM_REVIEW", pm_issues, "从产品视角审查 Dev 发现的问题"),
            ("DEV_REVIEW", dev_issues, "QA_REVIEW", qa_issues, "从测试视角审查 Dev 发现的问题"),
            ("QA_REVIEW", qa_issues, "PM_REVIEW", pm_issues, "从产品视角审查 QA 发现的问题"),
            ("QA_REVIEW", qa_issues, "DEV_REVIEW", dev_issues, "从技术视角审查 QA 发现的问题"),
        ]

        for source_name, source_issues, reviewer_name, _reviewer_own_issues, description in cross_pairs:
            if not source_issues:
                continue
            reviewer = self._get_agent(reviewer_name)
            source_label = AGENT_LABELS.get(source_name, source_name)
            reviewer_label = AGENT_LABELS.get(reviewer_name, reviewer_name)

            issues_json = json.dumps([
                {"index": idx, "title": iss.get("title"), "description": iss.get("description", "")[:300],
                 "severity": iss.get("severity"), "issue_type": iss.get("issue_type")}
                for idx, iss in enumerate(source_issues[:15])
            ], ensure_ascii=False)

            prompt = CROSS_REVIEW_PROMPT.format(
                role=reviewer_label,
                source_role=source_label,
                issues_json=issues_json,
            )

            try:
                raw = await asyncio.wait_for(
                    reviewer.run_json_mode(prompt, timeout=60.0),
                    timeout=60.0,
                )
                from app.services.agent_engine import parse_agent_response
                tags = self._parse_cross_tags(raw, source_name, reviewer_name)
                cross_tags.extend(tags)
            except Exception as e:
                logger.warning(f"Cross-review {reviewer_name}→{source_name} failed: {e}")

        return {"cross_review_tags": cross_tags}

    def _parse_cross_tags(self, raw: str, source_agent: str, reviewer_agent: str) -> list[dict]:
        import json, re
        try:
            data = json.loads(raw)
            tags = data.get("tags", [])
        except (json.JSONDecodeError, TypeError):
            m = re.search(r'\{[\s\S]*\}', raw)
            if m:
                try:
                    data = json.loads(m.group(0))
                    tags = data.get("tags", [])
                except Exception:
                    return []
            else:
                return []

        results = []
        for tag in tags:
            if not isinstance(tag, dict):
                continue
            results.append({
                "source_agent": source_agent,
                "reviewer_agent": reviewer_agent,
                "issue_index": tag.get("issue_index", -1),
                "tag": tag.get("tag", "SUPPLEMENTED"),
                "comment": tag.get("comment", ""),
            })
        return results

    def merge_issues_node(self, state: ReviewState) -> dict:
        all_issues = state.get("issues", [])
        cross_tags = state.get("cross_review_tags", [])

        tag_map: dict[int, list] = {}
        for ct in cross_tags:
            idx = ct.get("issue_index", -1)
            if idx not in tag_map:
                tag_map[idx] = []
            tag_map[idx].append(ct)

        for i, issue in enumerate(all_issues):
            conf = issue.get("confidence", 0.5)
            if conf >= 0.8:
                issue["confidence_label"] = "HIGH"
            elif conf >= 0.5:
                issue["confidence_label"] = "MEDIUM"
            else:
                issue["confidence_label"] = "LOW"
            issue["cross_review_tags"] = tag_map.get(i, [])

        return {"final_issues": all_issues, "session_status": "COMPLETED"}

    # ─── Graph builders ───

    def build_fast_graph(self):
        graph = StateGraph(ReviewState)
        graph.add_node("parse_prd", self.parse_prd_node)
        graph.add_node("pm_review", self.pm_fast_node)
        graph.add_node("dev_review", self.dev_fast_node)
        graph.add_node("qa_review", self.qa_fast_node)
        graph.add_node("merge_issues", self.merge_issues_node)

        graph.set_entry_point("parse_prd")
        graph.add_edge("parse_prd", "pm_review")
        graph.add_edge("parse_prd", "dev_review")
        graph.add_edge("parse_prd", "qa_review")
        graph.add_edge("pm_review", "merge_issues")
        graph.add_edge("dev_review", "merge_issues")
        graph.add_edge("qa_review", "merge_issues")
        graph.add_edge("merge_issues", END)

        return graph.compile()

    def build_debate_graph(self):
        graph = StateGraph(ReviewState)
        graph.add_node("parse_prd", self.parse_prd_node)
        graph.add_node("pm_review", self.pm_debate_node)
        graph.add_node("dev_review", self.dev_debate_node)
        graph.add_node("qa_review", self.qa_debate_node)
        graph.add_node("cross_review", self.cross_review_node)
        graph.add_node("merge_issues", self.merge_issues_node)

        graph.set_entry_point("parse_prd")
        graph.add_edge("parse_prd", "pm_review")
        graph.add_edge("pm_review", "dev_review")
        graph.add_edge("dev_review", "qa_review")
        graph.add_edge("qa_review", "cross_review")
        graph.add_edge("cross_review", "merge_issues")
        graph.add_edge("merge_issues", END)

        return graph.compile()

    def get_review_mode(self, agent_mode: str) -> ReviewMode:
        if self.config.get("enable_debate", False):
            return ReviewMode.DEBATE
        return ReviewMode.FAST

    async def run(
        self,
        prd_content: str,
        agent_mode: str = "DETERMINISTIC",
        session_id: str = "",
        project_id: str = "",
        prd_structure: dict = None,
        prd_images: list = None,
        user_answers: list = None,
    ) -> dict:
        initial_state: ReviewState = {
            "session_id": session_id,
            "project_id": project_id,
            "prd_content": prd_content,
            "prd_structure": prd_structure or {},
            "prd_images": prd_images or [],
            "agent_mode": agent_mode,
            "project_config": self.config,
            "issues": [],
            "follow_ups": [],
            "agent_statuses": {},
            "current_round": 0,
            "pm_issues": [],
            "dev_issues": [],
            "qa_issues": [],
            "cross_review_tags": [],
            "pending_follow_ups": [],
            "user_answers": user_answers or [],
            "final_issues": [],
            "session_status": "RUNNING",
        }

        mode = self.get_review_mode(agent_mode)
        logger.info(f"Orchestrator running in {mode.value} mode for session {session_id}")

        if mode == ReviewMode.DEBATE:
            graph = self.build_debate_graph()
            timeout = self.config.get("session_timeout_debate_min", 15) * 60
        else:
            graph = self.build_fast_graph()
            timeout = self.config.get("session_timeout_deterministic_min", 5) * 60

        try:
            await _send_progress(self.ws, session_id, "SYSTEM", "PARSING_PRDS",
                                 "正在解析PRD结构和图片...")
            result = await asyncio.wait_for(graph.ainvoke(initial_state), timeout=timeout)
            return result
        except asyncio.TimeoutError:
            initial_state["session_status"] = "TIMEOUT"
            return initial_state
