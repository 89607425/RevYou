# Phase 1 — Step 2: Execute（分步执行审查）

{role_prompt}

---

你正在按照审查计划对需求文档进行审查。本次聚焦以下焦点区域。

## 文档内容

{document}

## 审查计划

{review_plan}

## 当前焦点区域

{focus_area}

## 你的任务

针对上述焦点区域，仔细审查文档，找出具体问题。每个问题需要：
- **id**：用前缀+序号（如 PM-001, DEV-001, TEST-001）
- **severity**：critical(阻断) / major(高) / minor(中) / suggestion(建议)
- **location**：定位到章节，格式如 "§2.1 功能需求 / 第2段"
- **title**：一句话问题标题
- **description**：问题详细描述
- **suggestion**：具体修改建议

## 输出格式（严格 JSON）

```json
{
  "area": "焦点区域名",
  "issues": [
    {
      "id": "PM-001",
      "severity": "critical",
      "location": "§2.1 功能需求 / 第2段",
      "title": "一句话问题标题",
      "description": "问题详细描述",
      "suggestion": "具体修改建议"
    }
  ],
  "notes": "该区域的补充观察（可选）"
}
```

只输出 JSON，不要输出其他任何内容。