# Phase 1 — Step 3: Reflect（自检反思）

你是 {role} 视角的审查者，刚完成了对需求文档的审查。现在你需要自检审查质量。

## 审查计划

{review_plan}

## 已发现的全部问题

{findings}

## 你的任务

诚实地自我评估：

1. **coverage_gaps**：计划中的 focus_areas 是否全部覆盖了？有无漏审的区域？
2. **quality_issues**：哪些问题的 description 过于模糊或证据不足？列出 issue id
3. **false_positives**：哪些问题疑似过度标记（吹毛求疵）？列出 issue id
4. **needs_another_pass**：是否需要再补审一轮？
5. **gap_areas**：如果需要补审，列出需要重新审查的区域

## 输出格式（严格 JSON）

```json
{
  "coverage_gaps": ["未充分覆盖的区域描述"],
  "quality_issues": ["PM-003", "PM-007"],
  "false_positives": ["PM-005"],
  "needs_another_pass": true,
  "gap_areas": ["需要补审的区域：如'§4.2 异常处理描述不完整'"]
}
```

只输出 JSON，不要输出其他任何内容。