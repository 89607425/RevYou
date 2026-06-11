"""Agent engine: LangGraph-based parallel agent review system."""
import asyncio
import json
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import TypedDict, Annotated, Optional
from operator import add

from langgraph.graph import StateGraph, END

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── State Definition ───

class ReviewState(TypedDict):
    session_id: str
    project_id: str
    prd_content: str
    prd_structure: dict
    prd_images: list
    agent_mode: str
    project_config: dict

    issues: Annotated[list, add]
    follow_ups: Annotated[list, add]
    agent_statuses: dict
    current_round: int

    pending_follow_ups: list
    user_answers: list

    final_issues: list
    session_status: str


# ─── Agent Prompts ───

PM_SYSTEM_PROMPT = """你是一位资深产品经理，现在负责从产品视角审查PRD文档。你的目标是发现PRD中的逻辑漏洞、信息缺失和不一致之处。

## 审查维度
你必须从以下维度逐一审查：

### 1. 用户流程完整性
- 主流程是否有明确的起点和终点？
- 每个决策节点是否覆盖了所有分支（是/否/异常）？
- 是否存在"用户不知道下一步该做什么"的情况？

### 2. 状态流转
- 是否定义了完整的状态机（所有状态、转换条件、触发事件）？
- 是否存在不可达状态？是否存在无法退出的状态？
- 状态回退（如审批驳回、取消订单）是否定义？

### 3. 埋点缺失
- 核心用户行为是否有埋点定义？
- 业务漏斗的关键步骤是否有数据采集方案？

### 4. 文案一致性
- 同一概念在不同章节的用词是否一致？
- UI文案与功能描述是否匹配？

### 5. 边界条件
- 数值边界（最大值/最小值/默认值）是否定义？
- 空值/null/undefined的处理是否说明？
- 列表为空时的展示是否定义？

### 6. 异常流
- 操作失败后的处理是否定义？（如网络超时、服务端错误）
- 并发冲突的处理是否定义？
- 第三方服务不可用时的降级策略是否定义？

## 输出格式
对每个发现的问题，按以下JSON格式输出。请使用```json代码块包裹，以便解析：

```json
{
  "issues": [
    {
      "title": "问题标题（简明一句话，不超过30字）",
      "issue_type": "LOGIC_GAP",
      "severity": "HIGH",
      "description": "问题详细描述，用「」标注引用的PRD原文",
      "suggestion": "建议的解决方案",
      "prd_section": "对应PRD章节",
      "prd_quote": "PRD原文引用片段",
      "confidence": 0.85,
      "image_ref": null
    }
  ]
}
```

## 等级标准
- HIGH：逻辑矛盾/流程断链/可能导致线上事故/用户资金损失
- MEDIUM：信息缺失/边界未定义/可能导致开发返工
- LOW：文案不一致/格式问题/优化建议

## 约束
1. 每个问题的description必须引用PRD原文，用「」标注
2. 不输出与PRD内容无关的问题
3. 最多输出20个问题
4. 如果PRD质量较高，不要为了凑数而降低标准
"""

DEV_SYSTEM_PROMPT = """你是一位资深技术架构师，负责从技术视角审查PRD文档。发现技术风险、接口设计缺陷和实现障碍。

## 审查维度
### 1. 技术风险
- PRD中描述的功能在当前技术栈下是否可实现？是否有未评估的第三方依赖？

### 2. 接口依赖
- 接口契约是否定义（URL、Method、入参、出参、错误码）？
- 上下游接口是否对齐？是否有循环依赖？

### 3. 数据一致性
- 跨表/跨服务的数据更新是否有事务保障方案？
- 缓存与数据库的一致性策略是否定义？

### 4. 幂等问题
- 重复提交场景是否有幂等设计？
- 支付/库存等关键操作是否防重？

### 5. 并发问题
- 高并发场景是否有限流/队列方案？
- 竞态条件是否考虑？数据库锁策略是否说明？

### 6. 兼容性
- 是否涉及老版本兼容？数据迁移方案是否说明？灰度发布策略是否考虑？

## 输出格式
同PM Agent的JSON格式，issue_type使用：TECHNICAL_RISK / DATA_INCONSISTENCY / LOGIC_GAP

等级标准：
- HIGH：技术不可行/可能导致线上事故（数据丢失/资金损失）
- MEDIUM：技术方案不完整/可能导致返工
- LOW：技术建议优化/非关键兼容性问题

约束：不假设具体技术方案（除非PRD提及），只指出风险方向。最多20个问题。
"""

QA_SYSTEM_PROMPT = """你是一位资深测试工程师，负责从测试视角审查PRD文档。发现测试覆盖不足的地方，生成边界测试Case和异常流Case。

## 审查维度
### 1. 边界条件
- 数值边界、字符串边界、时间边界、数组边界的测试Case

### 2. 异常流程
- 操作失败路径、异常数据输入、第三方依赖失败、数据部分失败的处理

### 3. Case遗漏
- 状态流转全路径、权限边界、并发操作、回退操作

### 4. 状态覆盖
- 所有状态转换、状态回退、非法状态转换、状态超时的测试场景

## 输出格式
issue_type使用 TEST_MISSING。

suggestion字段必须包含具体的测试Case：
"建议补充以下测试Case：\n1. [前置条件] ...\n   [操作] ...\n   [预期] ..."

等级标准：
- HIGH：核心功能不可测试/存在必现缺陷路径
- MEDIUM：异常路径未覆盖/边界条件未定义
- LOW：非核心场景未覆盖

约束：每个问题必须包含至少一个具体测试Case。最多20个问题。
"""

AUTONOMOUS_APPEND = """
## 自主审查模式
你可以发起追问。如果发现PRD存在信息缺失导致无法判断问题是否存在，按以下格式输出追问：

```json
{
  "follow_ups": [
    {
      "question": "具体追问内容",
      "prd_section": "关联章节",
      "reason": "追问原因"
    }
  ]
}
```

追问规则：只在信息缺失导致无法判断时才追问；追问必须具体；最多5次追问。
"""

AGENT_PROMPTS = {
    "PM_REVIEW": PM_SYSTEM_PROMPT,
    "DEV_REVIEW": DEV_SYSTEM_PROMPT,
    "QA_REVIEW": QA_SYSTEM_PROMPT,
}


# ─── LLM Call Utilities ───

async def call_llm(system_prompt: str, user_content: str, model: str = "deepseek-v3") -> str:
    """Call LLM API. In MVP, uses langchain for model-agnostic calls.
    
    For now, returns a structured mock response indicating the service is ready
    but requires API keys configured. Real implementation will use the OpenAI-compatible
    APIs for DeepSeek, Qwen, and GPT-4o.
    """
    # TODO: Replace with real LLM call once API keys are configured
    # This stub returns an informative message - in production this would call the LLM API.
    
    try:
        from langchain_openai import ChatOpenAI
        
        if model == "deepseek-v3":
            llm = ChatOpenAI(
                model="deepseek-chat",
                api_key=settings.LLM_DEEPSEEK_API_KEY,
                base_url=settings.LLM_DEEPSEEK_BASE_URL,
                temperature=0.3,
                max_tokens=4096,
            )
        elif model in ("qwen-vl-max", "gpt-4o"):
            base = settings.LLM_QWEN_BASE_URL if "qwen" in model else settings.LLM_OPENAI_BASE_URL
            key = settings.LLM_QWEN_API_KEY if "qwen" in model else settings.LLM_OPENAI_API_KEY
            llm = ChatOpenAI(
                model=model,
                api_key=key,
                base_url=base,
                temperature=0.3,
                max_tokens=4096,
            )
        else:
            llm = ChatOpenAI(
                model="deepseek-chat",
                api_key=settings.LLM_DEEPSEEK_API_KEY,
                base_url=settings.LLM_DEEPSEEK_BASE_URL,
                temperature=0.3,
                max_tokens=4096,
            )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        response = await llm.ainvoke(messages)
        return response.content if hasattr(response, "content") else str(response)
    
    except Exception as e:
        logger.warning(f"LLM call failed ({model}): {e}")
        # Return mock data for development when API keys not configured
        return json.dumps({
            "issues": [{
                "title": f"[开发模式] LLM调用需要配置API Key ({model})",
                "issue_type": "LOGIC_GAP",
                "severity": "LOW",
                "description": f"LLM API Key 未配置或调用失败: {str(e)}。请检查 .env 文件中的 LLM 相关配置。",
                "suggestion": "配置有效的 LLM API Key 后重试",
                "prd_section": "系统配置",
                "prd_quote": "",
                "confidence": 0.3,
                "image_ref": None,
            }]
        }, ensure_ascii=False)


async def call_multimodal_model(image_path: str, prompt: str, model: str = "qwen-vl-max") -> Optional[str]:
    """Call multimodal model for image recognition."""
    try:
        from langchain_openai import ChatOpenAI
        import base64

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        llm = ChatOpenAI(
            model=model,
            api_key=settings.LLM_QWEN_API_KEY,
            base_url=settings.LLM_QWEN_BASE_URL,
            temperature=0.1,
            max_tokens=2048,
        )

        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
            ],
        }]
        response = await llm.ainvoke(messages)
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.warning(f"Multimodal call failed: {e}")
        return f"[图片识别失败: {str(e)}]"


# ─── JSON Parsing (Three-layer defense) ───

def parse_agent_response(raw: str, agent_name: str) -> list[dict]:
    """Parse Agent response using three-layer defense strategy."""
    # Layer 1: Direct JSON parse
    try:
        parsed = json.loads(raw)
        issues = parsed.get("issues", [])
        if isinstance(issues, list):
            return validate_and_normalize_issues(issues, agent_name)
    except (json.JSONDecodeError, TypeError):
        pass

    # Layer 2: Extract from markdown code block or find first JSON
    extracted = extract_json_from_response(raw)
    if extracted:
        try:
            parsed = json.loads(extracted)
            issues = parsed.get("issues", [])
            if isinstance(issues, list):
                return validate_and_normalize_issues(issues, agent_name)
        except (json.JSONDecodeError, TypeError):
            pass

    # Layer 3: Fallback - return as unstructured issue
    logger.warning(f"Agent {agent_name}: JSON parse failed, using fallback")
    return [{
        "title": f"[{agent_name}] 非结构化审查输出",
        "issue_type": "UNSTRUCTURED",
        "severity": "LOW",
        "description": raw[:2000],
        "suggestion": "AI输出格式异常，请人工审核",
        "prd_section": None,
        "prd_quote": None,
        "confidence": 0.3,
        "image_ref": None,
    }]


def extract_json_from_response(text: str) -> Optional[str]:
    """Extract JSON from LLM response (markdown code block or raw)."""
    # Try markdown code block
    pattern = r'```(?:json)?\s*\n([\s\S]*?)\n```'
    matches = re.findall(pattern, text)
    if matches:
        return max(matches, key=len).strip()

    # Try to find first complete JSON object or array
    bracket_match = re.search(r'\[[\s\S]*\]', text)
    brace_match = re.search(r'\{[\s\S]*\}', text)
    candidates = []
    if bracket_match:
        candidates.append(bracket_match.group(0))
    if brace_match:
        candidates.append(brace_match.group(0))
    if candidates:
        return min(candidates, key=lambda c: text.index(c))
    return None


def validate_and_normalize_issues(issues: list, agent_name: str) -> list[dict]:
    """Validate and normalize issue fields."""
    valid_types = {"TECHNICAL_RISK", "LOGIC_GAP", "TEST_MISSING", "DATA_INCONSISTENCY", "UNSTRUCTURED"}
    valid_severities = {"HIGH", "MEDIUM", "LOW"}

    normalized = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        normalized.append({
            "title": str(issue.get("title", "未知问题"))[:200],
            "issue_type": issue.get("issue_type", "LOGIC_GAP") if issue.get("issue_type") in valid_types else "LOGIC_GAP",
            "severity": issue.get("severity", "MEDIUM") if issue.get("severity") in valid_severities else "MEDIUM",
            "description": str(issue.get("description", ""))[:2000],
            "suggestion": str(issue.get("suggestion", ""))[:2000],
            "prd_section": str(issue.get("prd_section", "")),
            "prd_quote": str(issue.get("prd_quote", "")),
            "confidence": max(0.0, min(1.0, float(issue.get("confidence", 0.5)))),
            "image_ref": issue.get("image_ref"),
        })
    return normalized[:30]


def extract_follow_ups_from_response(raw: str) -> list[dict]:
    """Extract follow-up questions from autonomous mode response."""
    try:
        parsed = json.loads(raw)
        return parsed.get("follow_ups", [])
    except (json.JSONDecodeError, TypeError):
        pass

    extracted = extract_json_from_response(raw)
    if extracted:
        try:
            parsed = json.loads(extracted)
            return parsed.get("follow_ups", [])
        except (json.JSONDecodeError, TypeError):
            pass
    return []


# ─── Agent Nodes ───

async def parse_prd_node(state: ReviewState) -> dict:
    """Parse PRD: recognize images, prepare content for agents."""
    prd_images = state.get("prd_images", [])
    
    for img in prd_images:
        if img.get("recognition_status") == "PENDING" and img.get("local_path"):
            try:
                result = await call_multimodal_model(
                    img["local_path"],
                    "请描述这张图片的内容，重点关注：流程步骤、状态转换、数据流向、关键节点。以结构化文本输出。"
                )
                if result:
                    img["recognition_status"] = "COMPLETED"
                    img["recognition_result"] = result
            except Exception:
                img["recognition_status"] = "FAILED"

    from app.services.prd_parser import enrich_prd_with_image_text
    enriched = enrich_prd_with_image_text(state["prd_content"], prd_images)

    return {
        "prd_content": enriched,
        "prd_images": prd_images,
        "agent_statuses": {"PM_REVIEW": "PENDING", "DEV_REVIEW": "PENDING", "QA_REVIEW": "PENDING"},
        "issues": [],
        "follow_ups": [],
        "current_round": 1,
        "pending_follow_ups": [],
        "user_answers": [],
    }


async def pm_review_node(state: ReviewState) -> dict:
    return await _run_single_agent(state, "PM_REVIEW")


async def dev_review_node(state: ReviewState) -> dict:
    return await _run_single_agent(state, "DEV_REVIEW")


async def qa_review_node(state: ReviewState) -> dict:
    return await _run_single_agent(state, "QA_REVIEW")


async def _run_single_agent(state: ReviewState, agent_name: str) -> dict:
    """Execute a single agent review call."""
    config = state.get("project_config", {})
    model = config.get("text_model", "deepseek-v3")
    has_images = any(img.get("recognition_status") == "COMPLETED" for img in state.get("prd_images", []))
    if has_images and config.get("auto_switch_model", True):
        model = config.get("multimodal_model", "qwen-vl-max")

    system_prompt = AGENT_PROMPTS[agent_name]
    if state["agent_mode"] == "AUTONOMOUS":
        system_prompt += AUTONOMOUS_APPEND

    user_content = f"请审查以下PRD文档：\n\n{state['prd_content'][:30000]}"
    if state.get("user_answers"):
        user_content += "\n\n## 用户补充信息\n"
        for ans in state["user_answers"]:
            user_content += f"- {ans.get('answer', '')}\n"

    try:
        response = await asyncio.wait_for(
            call_llm(system_prompt, user_content, model),
            timeout=120.0,
        )
    except asyncio.TimeoutError:
        return {
            "issues": [{"title": f"[{agent_name}] 审查超时", "issue_type": "LOGIC_GAP", "severity": "LOW",
                        "description": "Agent审查超时", "suggestion": "请重试", "confidence": 0.3}],
        }

    issues = parse_agent_response(response, agent_name)
    follow_ups = []
    if state["agent_mode"] == "AUTONOMOUS":
        follow_ups = extract_follow_ups_from_response(response)[:5]

    agent_statuses = dict(state.get("agent_statuses", {}))
    agent_statuses[agent_name] = "COMPLETED"

    return {"issues": issues, "follow_ups": follow_ups, "agent_statuses": agent_statuses}


def merge_issues_node(state: ReviewState) -> dict:
    """Merge and deduplicate issues from all agents."""
    all_issues = state.get("issues", [])
    
    # Calculate confidence labels
    for issue in all_issues:
        conf = issue.get("confidence", 0.5)
        if conf >= 0.8:
            issue["confidence_label"] = "HIGH"
        elif conf >= 0.5:
            issue["confidence_label"] = "MEDIUM"
        else:
            issue["confidence_label"] = "LOW"

    return {"final_issues": all_issues, "session_status": "COMPLETED"}


# ─── Graph Builders ───

def build_deterministic_graph() -> StateGraph:
    """Build the deterministic (single-round) review graph."""
    graph = StateGraph(ReviewState)

    graph.add_node("parse_prd", parse_prd_node)
    graph.add_node("pm_review", pm_review_node)
    graph.add_node("dev_review", dev_review_node)
    graph.add_node("qa_review", qa_review_node)
    graph.add_node("merge_issues", merge_issues_node)

    graph.set_entry_point("parse_prd")

    # Parallel edges: parse -> three agents
    graph.add_edge("parse_prd", "pm_review")
    graph.add_edge("parse_prd", "dev_review")
    graph.add_edge("parse_prd", "qa_review")

    # Converge: agents -> merge
    graph.add_edge("pm_review", "merge_issues")
    graph.add_edge("dev_review", "merge_issues")
    graph.add_edge("qa_review", "merge_issues")

    graph.add_edge("merge_issues", END)

    return graph.compile()


def build_autonomous_graph() -> StateGraph:
    """Build the autonomous (multi-round with follow-ups) review graph.
    
    For MVP, uses a similar structure to deterministic but allows
    follow-up extraction and re-review cycles.
    Currently placeholder for Phase 7 full implementation.
    """
    # MVP: use deterministic graph for now, autonomous mode details
    # will be fully implemented in Phase 7
    return build_deterministic_graph()


async def run_review(
    session_id: str,
    project_id: str,
    prd_content: str,
    prd_structure: dict,
    prd_images: list,
    agent_mode: str,
    project_config: dict,
) -> dict:
    """Run the review process and return results."""
    initial_state = ReviewState(
        session_id=session_id,
        project_id=project_id,
        prd_content=prd_content,
        prd_structure=prd_structure or {},
        prd_images=prd_images or [],
        agent_mode=agent_mode,
        project_config=project_config,
        issues=[],
        follow_ups=[],
        agent_statuses={},
        current_round=0,
        pending_follow_ups=[],
        user_answers=[],
        final_issues=[],
        session_status="RUNNING",
    )

    if agent_mode == "AUTONOMOUS":
        graph = build_autonomous_graph()
    else:
        graph = build_deterministic_graph()

    try:
        result = await asyncio.wait_for(
            graph.ainvoke(initial_state),
            timeout=600.0,
        )
        return result
    except asyncio.TimeoutError:
        initial_state["session_status"] = "TIMEOUT"
        return initial_state
