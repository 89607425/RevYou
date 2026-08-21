# Phase 2 — Step 1: Plan（交叉审查规划）

{role_prompt}

---

你已完成 Phase 1 独立审查。现在你看到了另外两个视角的审查发现。你的任务：分析同行的发现揭示了你的什么盲区，然后规划交叉审查策略。

## 文档内容

{document}

## 你的 Phase 1 审查计划与发现

{my_phase1}

## 同行 Agent 的 Phase 1 发现

{peer_findings}

## 你的任务

1. **peer_insight_analysis**：同行的发现暴露了你的什么盲区？哪些区域你没审到？
2. **re_review_targets**：基于同行发现，你需要重新审视哪些文档区域？
3. **my_weakness_check**：你的哪些结论可能站不住脚？哪些可能被同行挑战？

## 输出格式（严格 JSON）

```json
{
  "peer_insight_analysis": [
    "同行DEV-003发现的数据一致性问题暴露了我没审跨模块数据流转的盲区"
  ],
  "re_review_targets": [
    "§3.2 跨模块数据流转场景",
    "§5.0 验收标准的完整性"
  ],
  "my_weakness_check": [
    "PM-002 我说的范围边界缺失，可能DEV视角看是有技术约束的"
  ]
}
```

只输出 JSON，不要输出其他任何内容。