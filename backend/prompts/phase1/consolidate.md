# Phase 1 — Step 5: Consolidate（汇总定稿）

你是 {role} 视角的审查者，已完成全部审查（含补审）。现在需要汇总定稿。

## 全部发现

{all_findings}

## 自检结论

{reflect_result}

## 你的任务

1. 剔除自判的 false_positives 中的问题
2. 合并重复问题
3. 给出最终严重度评定
4. 写出总体评价(verdict)、亮点(highlights)、评分(overall_score 0-100)
5. 为每个保留的问题分配最终 id（按严重度排序，critical 在前）

## 输出控制（重要）

- **最多保留 15 个最重要的问题**；优先保留 critical/major
- 每个 description 和 suggestion 控制在 150 字以内，直击要点
- verdict 控制在 120 字以内

## 输出格式（严格 JSON）

```json
{
  "role": "{role}",
  "overall_score": 72,
  "verdict": "总体评价……",
  "highlights": ["亮点1", "亮点2"],
  "issues": [
    {
      "id": "PM-001",
      "severity": "critical",
      "location": "§2.1 功能需求 / 第2段",
      "title": "一句话问题标题",
      "description": "问题详细描述",
      "suggestion": "具体修改建议"
    }
  ]
}
```

只输出 JSON，不要输出其他任何内容。