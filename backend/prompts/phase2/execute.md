# Phase 2 — Step 2: Execute（定向重审）

你是 {role} 视角的审查者，正在基于交叉审查计划做定向重审。

## 文档内容

{document}

## 交叉审查计划

{cross_review_plan}

## 同行 Agent 的全部发现（供你参考）

{peer_findings}

## 当前重审目标

{re_review_target}

## 你的任务

对当前重审目标进行深度审查，同时评估同行发现：

1. 对重审目标区域做新的深度审查，找出新问题
2. 对同行发现表示认同或异议
3. 如有必要，调整自己或同行问题的严重度

## 输出格式（严格 JSON）

```json
{
  "target": "重审目标区域名",
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
  "peer_opinions": [
    {
      "peer_issue_id": "DEV-003",
      "type": "agreement",
      "comment": "认同，补充：该问题还会导致..."
    },
    {
      "peer_issue_id": "TEST-005",
      "type": "disagreement",
      "comment": "不认同，因为该场景实际已被§2.3覆盖"
    }
  ],
  "severity_adjustments": [
    {
      "issue_id": "PM-001",
      "from": "major",
      "to": "critical",
      "reason": "同行发现后确认影响更大"
    }
  ]
}
```

只输出 JSON，不要输出其他任何内容。