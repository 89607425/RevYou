# Phase 1 — Step 1: Plan（自主规划）

{role_prompt}

---

你正在为以下需求文档制定审查策略。请先理解文档内容，然后自主规划你的审查计划。

## 文档内容

{document}

## 你的任务

分析这份文档，输出你的审查策略。你必须：

1. **document_analysis**：判断文档类型（UI/数据/API/业务逻辑等），给出复杂度评分(1-5)，并记录关键观察
2. **risk_areas**：识别这份文档特有的高风险区域——不是泛泛而谈，要指向具体章节和段落
3. **focus_areas**：生成有序的审查焦点列表，每项含 area + 具体审查问题 questions[] + 关联章节 related_sections
4. **depth_assessment**：评估需要几轮审查（简单文档=1，中等=2，复杂=3）

## 输出格式（严格 JSON）

```json
{
  "document_analysis": {
    "doc_type": "UI交互/数据处理/API接口/业务逻辑/其他",
    "complexity_score": 3,
    "key_observation": "一句话概括文档的主要特征和核心风险"
  },
  "risk_areas": [
    {
      "area": "如：验收标准缺失",
      "reason": "为什么这是风险",
      "evidence_location": "如：§3.1 功能需求"
    }
  ],
  "focus_areas": [
    {
      "area": "如：功能完整性",
      "questions": ["问题1", "问题2"],
      "related_sections": ["§3.1", "§3.2"]
    }
  ],
  "depth_assessment": 2
}
```

只输出 JSON，不要输出其他任何内容。