"""End-to-end test for AgentRunner with mocked LLM.

Verifies the Plan → Execute → Reflect → Adjust → Consolidate loop
works correctly without a real LLM API key.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch

from app.services.agent_runner import AgentRunner
from app.services.doc_parser import DocParser
from app.models.review import AgentPhase1Report


SAMPLE_MD = """# 订单导出功能需求

## 1. 背景
运营需要导出订单数据做分析。

## 2. 功能需求
支持按时间范围筛选订单，点击导出按钮生成 Excel 文件。

## 3. 验收标准
导出功能可用。
"""


def mock_llm_response(user_prompt: str) -> dict:
    """Return appropriate mock JSON based on which step is being called."""
    if "制定审查策略" in user_prompt:
        # Plan step
        return {
            "document_analysis": {
                "doc_type": "功能需求",
                "complexity_score": 2,
                "key_observation": "验收标准过于简单",
            },
            "risk_areas": [
                {"area": "验收标准", "reason": "不可度量", "evidence_location": "§3"}
            ],
            "focus_areas": [
                {
                    "area": "验收标准",
                    "questions": ["是否可度量？"],
                    "related_sections": ["§3"],
                }
            ],
            "depth_assessment": 1,
        }
    elif "汇总定稿" in user_prompt:
        # Consolidate step (must be checked BEFORE reflect, since the
        # consolidate template also contains "自检结论")
        return {
            "role": "product_manager",
            "overall_score": 65,
            "verdict": "验收标准需改进",
            "highlights": ["背景清晰"],
            "issues": [
                {
                    "id": "PM-001",
                    "severity": "major",
                    "location": "§3 验收标准",
                    "title": "验收标准不可度量",
                    "description": "'导出功能可用'无法验证",
                    "suggestion": "改为具体的验收标准",
                }
            ],
        }
    elif "针对上述焦点区域" in user_prompt or "焦点区域" in user_prompt:
        # Execute step
        return {
            "area": "验收标准",
            "issues": [
                {
                    "id": "PM-001",
                    "severity": "major",
                    "location": "§3 验收标准",
                    "title": "验收标准不可度量",
                    "description": "'导出功能可用'无法验证",
                    "suggestion": "改为具体的验收标准",
                }
            ],
            "notes": "",
        }
    elif "自我评估" in user_prompt or "自检" in user_prompt:
        # Reflect step
        return {
            "coverage_gaps": [],
            "quality_issues": [],
            "false_positives": [],
            "needs_another_pass": False,
            "gap_areas": [],
        }
    else:
        return {}


@pytest.mark.asyncio
async def test_agent_runner_phase1_loop():
    """Test the full Phase 1 loop with mocked LLM."""
    doc = DocParser.parse_markdown(SAMPLE_MD, "订单导出需求.md")

    with patch("app.services.agent_runner.llm_client") as mock_client:
        async def mock_complete_json(system_prompt, user_prompt, **kwargs):
            return mock_llm_response(user_prompt)

        mock_client.complete_json = AsyncMock(side_effect=mock_complete_json)

        runner = AgentRunner(role="product_manager", document=doc)
        report = await runner.run_phase1()

        # Verify the loop executed correctly
        assert isinstance(report, AgentPhase1Report)
        assert report.role == "product_manager"
        assert report.overall_score == 65
        assert len(report.issues) == 1
        assert report.issues[0].id == "PM-001"
        assert report.issues[0].severity.value == "major"

        # Verify thinking trace attached
        assert report.review_plan is not None
        assert report.review_plan.focus_areas[0].area == "验收标准"
        assert report.reflect_result is not None
        assert report.reflect_result.needs_another_pass is False

        # Verify call count: Plan(1) + Execute(1) + Reflect(1) + Consolidate(1) = 4
        assert report.call_count == 4


@pytest.mark.asyncio
async def test_agent_runner_adjust_loop():
    """Test that the Reflect → Adjust loop triggers when gaps found."""
    doc = DocParser.parse_markdown(SAMPLE_MD)
    reflect_call_count = 0

    with patch("app.services.agent_runner.llm_client") as mock_client:
        async def mock_complete_json(system_prompt, user_prompt, **kwargs):
            nonlocal reflect_call_count
            if "制定审查策略" in user_prompt:
                return {
                    "document_analysis": {
                        "doc_type": "功能需求", "complexity_score": 2,
                        "key_observation": "test",
                    },
                    "risk_areas": [],
                    "focus_areas": [{"area": "A", "questions": [], "related_sections": []}],
                    "depth_assessment": 1,
                }
            elif "汇总定稿" in user_prompt:
                return {
                    "role": "product_manager", "overall_score": 70,
                    "verdict": "OK", "highlights": [],
                    "issues": [{"id": "PM-001", "severity": "minor",
                                "location": "§1", "title": "t",
                                "description": "d", "suggestion": "s"}],
                }
            elif "焦点区域" in user_prompt:
                return {"area": "A", "issues": [], "notes": ""}
            elif "自检" in user_prompt:
                reflect_call_count += 1
                if reflect_call_count == 1:
                    # First reflect: needs another pass
                    return {
                        "coverage_gaps": ["区域B未覆盖"],
                        "quality_issues": [],
                        "false_positives": [],
                        "needs_another_pass": True,
                        "gap_areas": ["区域B"],
                    }
                else:
                    # Second reflect: done
                    return {
                        "coverage_gaps": [], "quality_issues": [],
                        "false_positives": [], "needs_another_pass": False,
                        "gap_areas": [],
                    }
            elif "汇总定稿" in user_prompt:
                return {
                    "role": "product_manager", "overall_score": 70,
                    "verdict": "OK", "highlights": [],
                    "issues": [{"id": "PM-001", "severity": "minor",
                                "location": "§1", "title": "t",
                                "description": "d", "suggestion": "s"}],
                }
            return {}

        mock_client.complete_json = AsyncMock(side_effect=mock_complete_json)

        runner = AgentRunner(role="product_manager", document=doc)
        report = await runner.run_phase1()

        # Plan(1) + Execute(1) + Reflect(1) + Adjust Execute(1) + Reflect(1) + Consolidate(1) = 6
        assert report.call_count == 6
        assert reflect_call_count == 2
