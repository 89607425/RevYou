# Phase 2 — Reflect（交叉审查自检）

你是 {role} 视角的审查者，刚完成了交叉审查。自检你的交叉审查质量。

## 交叉审查计划

{cross_review_plan}

## 你的交叉审查发现

{cross_findings}

## 你的任务

1. **coverage_gaps**：re_review_targets 是否全部重审了？
2. **quality_issues**：有无新增问题过于模糊？
3. **false_positives**：有无过度同意同行观点（没有自己判断）？
4. **needs_another_pass**：是否需要再补审？
5. **gap_areas**：需补审的区域

## 输出格式（严格 JSON）

```json
{
  "coverage_gaps": ["未重审的区域"],
  "quality_issues": ["PM-012"],
  "false_positives": [],
  "needs_another_pass": false,
  "gap_areas": []
}
```

只输出 JSON，不要输出其他任何内容。