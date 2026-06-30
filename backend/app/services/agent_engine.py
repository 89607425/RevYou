"""Agent engine: compatibility layer delegating to the multi-agent orchestrator.

Maintains backward compatibility for all public functions while
internally using the new DebateOrchestrator with real agent instances.
"""

import asyncio
import json
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import TypedDict, Annotated, Optional
from operator import add

def _merge_dicts(a: dict, b: dict) -> dict:
    return {**a, **b}

from langgraph.graph import StateGraph, END

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── Model Provider Map (shared utility) ───

MODEL_PROVIDER_MAP = {
    "deepseek-v3": {
        "api_key_attr": "LLM_DEEPSEEK_API_KEY",
        "base_url_attr": "LLM_DEEPSEEK_BASE_URL",
        "model_id": "deepseek-chat",
    },
    "glm-4": {
        "api_key_attr": "LLM_ZHIPU_API_KEY",
        "base_url_attr": "LLM_ZHIPU_BASE_URL",
        "model_id": "glm-4-plus",
    },
    "glm-4v-plus": {
        "api_key_attr": "LLM_ZHIPU_API_KEY",
        "base_url_attr": "LLM_ZHIPU_BASE_URL",
        "model_id": "glm-4v-plus",
    },
    "glm-4v-flash": {
        "api_key_attr": "LLM_ZHIPU_API_KEY",
        "base_url_attr": "LLM_ZHIPU_BASE_URL",
        "model_id": "glm-4v-flash",
    },
    "qwen-vl-max": {
        "api_key_attr": "LLM_SILICONFLOW_API_KEY",
        "base_url_attr": "LLM_SILICONFLOW_BASE_URL",
        "model_id": "deepseek-ai/DeepSeek-V3",
    },
    "gemini-2.0-flash": {
        "api_key_attr": "LLM_GEMINI_API_KEY",
        "base_url_attr": "LLM_GEMINI_BASE_URL",
        "model_id": "gemini-2.0-flash",
    },
    "gpt-4o": {
        "api_key_attr": "LLM_SILICONFLOW_API_KEY",
        "base_url_attr": "LLM_SILICONFLOW_BASE_URL",
        "model_id": "deepseek-ai/DeepSeek-V3",
    },
}

AGENT_MODEL_KEY_MAP = {
    "PM_REVIEW": "pm_model",
    "DEV_REVIEW": "dev_model",
    "QA_REVIEW": "qa_model",
}


def _get_provider_for_model(model: str) -> dict:
    if model not in MODEL_PROVIDER_MAP:
        logger.warning(f"Unknown model '{model}', falling back to deepseek-v3")
        model = "deepseek-v3"
    entry = MODEL_PROVIDER_MAP[model]
    api_key = getattr(settings, entry["api_key_attr"], "")
    base_url = getattr(settings, entry["base_url_attr"], settings.LLM_BASE_URL)
    return {"api_key": api_key, "base_url": base_url, "model_id": entry["model_id"]}


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
    agent_statuses: Annotated[dict, _merge_dicts]
    current_round: int

    pending_follow_ups: list
    user_answers: list

    final_issues: list
    session_status: str


# ─── Agent Prompts (kept for backward compat / standalone use) ───

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
    """Call LLM API via the appropriate provider for the given model."""
    try:
        from langchain_openai import ChatOpenAI

        provider = _get_provider_for_model(model)

        llm = ChatOpenAI(
            model=provider["model_id"],
            openai_api_key=provider["api_key"],
            base_url=provider["base_url"],
            temperature=0.3,
            max_tokens=8192,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        response = await llm.ainvoke(messages)
        return response.content if hasattr(response, "content") else str(response)

    except Exception as e:
        logger.warning(f"LLM call failed ({model}): {e}")
        return json.dumps({
            "issues": [{
                "title": f"LLM调用失败 ({model})",
                "issue_type": "LOGIC_GAP",
                "severity": "HIGH",
                "description": f"调用失败: {str(e)[:500]}",
                "suggestion": "检查 API Key 配置和网络连接后重试",
                "prd_section": "",
                "prd_quote": "",
                "confidence": 0.3,
                "image_ref": None,
            }]
        }, ensure_ascii=False)


async def call_multimodal_model(image_path: str, prompt: str, model: str = "glm-4v-plus") -> Optional[str]:
    """Call multimodal model for image recognition."""
    try:
        from langchain_openai import ChatOpenAI
        import base64

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        provider = _get_provider_for_model(model)

        llm = ChatOpenAI(
            model=provider["model_id"],
            openai_api_key=provider["api_key"],
            base_url=provider["base_url"],
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


# ─── JSON Parsing (Four-layer defense) ───

def parse_agent_response(raw: str, agent_name: str) -> list[dict]:
    """Parse Agent response using four-layer defense strategy."""
    if not raw or not raw.strip():
        return [{"title": f"[{agent_name}] 空响应", "issue_type": "UNSTRUCTURED", "severity": "LOW",
                 "description": "Agent 返回了空内容", "suggestion": "", "confidence": 0.1,
                 "prd_section": None, "prd_quote": None, "image_ref": None}]

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return validate_and_normalize_issues(parsed, agent_name)
        issues = parsed.get("issues", [])
        if isinstance(issues, list):
            return validate_and_normalize_issues(issues, agent_name)
    except (json.JSONDecodeError, TypeError):
        pass

    extracted = extract_json_from_response(raw)
    if extracted:
        try:
            parsed = json.loads(extracted)
            if isinstance(parsed, list):
                return validate_and_normalize_issues(parsed, agent_name)
            issues = parsed.get("issues", [])
            if isinstance(issues, list):
                return validate_and_normalize_issues(issues, agent_name)
        except (json.JSONDecodeError, TypeError):
            pass

    candidates = []
    fence_match = re.search(r'```(?:json)?\s*\n([\s\S]+)', raw)
    if fence_match:
        candidates.append(fence_match.group(1).strip())
    if extracted:
        candidates.append(extracted)
    json_start = re.search(r'[\{\[]', raw)
    if json_start:
        candidates.append(raw[json_start.start():])
    if not candidates:
        candidates.append(raw)

    fixed = None
    for candidate in candidates:
        fixed = fix_truncated_json(candidate)
        if fixed:
            break

    if fixed:
        try:
            parsed = json.loads(fixed)
            if isinstance(parsed, list):
                return validate_and_normalize_issues(parsed, agent_name)
            issues = parsed.get("issues", [])
            if isinstance(issues, list) and issues:
                logger.info(f"Agent {agent_name}: recovered {len(issues)} issues from truncated JSON")
                return validate_and_normalize_issues(issues, agent_name)
        except (json.JSONDecodeError, TypeError):
            pass

    logger.warning(f"Agent {agent_name}: all JSON parse layers failed, raw length={len(raw)}")
    return [{
        "title": f"[{agent_name}] AI输出格式异常",
        "issue_type": "UNSTRUCTURED",
        "severity": "LOW",
        "description": raw[:2000],
        "suggestion": f"响应长度 {len(raw)} 字符，未能解析为JSON，请人工审核",
        "prd_section": None,
        "prd_quote": None,
        "confidence": 0.3,
        "image_ref": None,
    }]


def fix_truncated_json(text: str) -> Optional[str]:
    if not text:
        return None
    text = text.strip()
    if not (text.startswith("{") or text.startswith("[")):
        return None

    result = _try_fix_json(text)
    if result:
        return result

    stripped = text
    for _ in range(3):
        stripped = _strip_trailing_incomplete(stripped)
        if stripped == text:
            break
        result = _try_fix_json(stripped)
        if result:
            return result

    return None


def _try_fix_json(text: str) -> Optional[str]:
    stack = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ("{", "["):
            stack.append(ch)
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()

    suffix = ""
    if in_string:
        suffix += '"'
        if stack and stack[-1] == "{":
            suffix += ':"?"'
            stack.pop()
    closers = {"{": "}", "[": "]"}
    suffix += "".join(closers[c] for c in reversed(stack))
    if not suffix:
        return None

    fixed = text.rstrip().rstrip(",") + suffix
    try:
        __import__('json').loads(fixed)
        return fixed
    except (ValueError, __import__('json').JSONDecodeError):
        return None


def _strip_trailing_incomplete(text: str) -> str:
    last_comma = text.rfind(",")
    last_close_brace = text.rfind("}")
    last_close_bracket = text.rfind("]")
    safe_pos = max(last_comma, last_close_brace, last_close_bracket)
    if safe_pos >= 0:
        return text[:safe_pos + 1].rstrip()
    for i, ch in enumerate(text):
        if ch in ("{", "["):
            return text[:i + 1]
    return text


def extract_json_from_response(text: str) -> Optional[str]:
    pattern = r'```(?:json)?\s*\n([\s\S]*?)\n\s*```'
    matches = re.findall(pattern, text)
    if matches:
        return max(matches, key=len).strip()

    clean = re.sub(r'^```(?:json)?\s*\n', '', text.strip())
    bracket_match = re.search(r'\[[\s\S]*\]', clean)
    brace_match = re.search(r'\{[\s\S]*\}', clean)
    candidates = []
    if bracket_match:
        candidates.append(bracket_match.group(0))
    if brace_match:
        candidates.append(brace_match.group(0))
    if candidates:
        return min(candidates, key=lambda c: clean.index(c))
    return None


def validate_and_normalize_issues(issues: list, agent_name: str) -> list[dict]:
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


# ─── Legacy Graph Builders (kept for backward compat, delegate to orchestrator) ───

def build_deterministic_graph():
    """Legacy: returns a compiled LangGraph. Use run_review() instead."""
    from app.agents.orchestrator import DebateOrchestrator
    orch = DebateOrchestrator({})
    return orch.build_fast_graph()


def build_autonomous_graph():
    """Legacy: returns the fast graph. Autonomous mode handled via orchestrator."""
    return build_deterministic_graph()


# ─── Main Entry Point ───

async def run_review(
    prd_content: str,
    agent_mode: str = "DETERMINISTIC",
    config: dict = None,
    session_id: str = "",
    project_id: str = "",
    prd_structure: dict = None,
    prd_images: list = None,
    ws_manager=None,
    user_answers: list = None,
) -> dict:
    """Run the multi-agent review process.

    Now delegates to DebateOrchestrator which supports:
    - FAST mode: parallel PM/Dev/QA review (5 min timeout)
    - DEBATE mode: serial review with cross-review tagging (enabled via config.enable_debate=True)
    - Optional function-calling tool use for each agent
    - Cross-review tagging in debate mode
    """
    from app.agents.orchestrator import DebateOrchestrator

    orch = DebateOrchestrator(
        project_config=config or {},
        ws_manager=ws_manager,
    )

    try:
        if ws_manager and session_id:
            await ws_manager.send_message(session_id, "AGENT_THINKING", {
                "agent": "SYSTEM",
                "message": "正在启动多 Agent 审查...",
                "phase": "STARTING",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        result = await orch.run(
            prd_content=prd_content,
            agent_mode=agent_mode,
            session_id=session_id,
            project_id=project_id,
            prd_structure=prd_structure or {},
            prd_images=prd_images or [],
            user_answers=user_answers or [],
        )
        return result
    except asyncio.TimeoutError:
        return {
            "session_id": session_id,
            "project_id": project_id,
            "prd_content": prd_content,
            "prd_structure": prd_structure or {},
            "prd_images": prd_images or [],
            "agent_mode": agent_mode,
            "project_config": config or {},
            "issues": [],
            "follow_ups": [],
            "agent_statuses": {},
            "current_round": 0,
            "final_issues": [],
            "session_status": "TIMEOUT",
        }
