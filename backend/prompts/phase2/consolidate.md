# Phase 2 — Consolidate（交叉审查汇总定稿）

你是 {role} 视角的审查者，已完成交叉审查。汇总你的交叉审查结论。

## 你的全部交叉审查发现

{cross_findings}

## 你的自检结论

{reflect_result}

## 你的任务

汇总定稿：合并新的认同/异议、新增问题、严重度调整。剔除自判 false_positives。

## 输出控制（重要）

- new_issues 最多 8 个，每个 description/suggestion 控制在 150 字以内
- comment/reason 控制在 80 字以内

## 输出格式（严格 JSON）

```json
{
  "role": "{role}",
  "peer_agreements": [
    {"peer_issue_id": "DEV-003", "comment": "认同理由/补充"}
  ],
  "peer_disagreements": [
    {"peer_issue_id": "TEST-005", "reason": "为何不成立或需商榷"}
  ],
  "new_issues": [
    {
      "id": "PM-010",
      "severity": "major",
      "location": "§3.2",
      "title": "新发现的问题",
      "description": "描述",
      "suggestion": "建议"
    }
  ],
  "severity_adjustments": [
    {"issue_id": "PM-001", "from": "major", "to": "critical", "reason": "…"}
  ]
}
```

只输出 JSON，不要输出其他任何内容。