# Multi-Agent 升级路线

## Phase 1: Agent 实体化（让 Agent 成为独立对象）

- [ ] 定义 `BaseAgent` 类：封装 name、system_prompt、model、tools、memory
  - 文件：`backend/app/agents/base_agent.py`
- [ ] 实现 `tool_registry`：每个 Agent 可注册自己的工具集（TAPD查询、DB查询、文档检索）
  - 文件：`backend/app/agents/tools.py`
- [ ] 改造 `_run_single_agent()` → `BaseAgent.run()`：Agent 自主决定是否调 tool、是否追问

## Phase 2: Agent 间对话（交叉审查）

- [ ] 实现 `DebateOrchestrator`：多 Agent 轮询对话，而非并行独立执行
  - 流程：PM 先审 → Dev 基于 PM 的发现再审 → QA 基于前两者再审 → 汇总辩论纪要
  - 文件：`backend/app/agents/orchestrator.py`
- [ ] 实现 `cross_review` 机制：Agent 可以对他人的 issue 打 tag（确认/质疑/补充用例）
- [ ] 改造 graph：`parse → PM → Dev → QA → cross_review → merge`

## Phase 3: 工具调用能力

- [ ] PM Agent 工具：TAPD 需求查询、历史项目对比
- [ ] Dev Agent 工具：技术文档检索、接口定义查询
- [ ] QA Agent 工具：历史 bug 库检索、测试用例生成
- [ ] 实现 `tool_use` 循环：Agent 在分析过程中可多次调用工具获取上下文

## Phase 4: 自主交互模式（补齐 STUB）

- [ ] 实现 `human_in_loop` 节点：Agent 生成追问 → `interrupt()` 等待用户回答 → 恢复执行
- [ ] 实现 `re_review_round`：基于用户回答，Agent 重新审查（最多3轮）
- [ ] 实现 `check_round` 路由：判断是否还有 unresolved 问题，决定继续或结束

## Phase 5: Agent 记忆与持久化

- [ ] 实现 `AgentMemory`：存储 Agent 历史审查记录、常见问题模式
- [ ] 实现 `KnowledgeBase`：基于历史 issue 做向量检索，新 PRD 审查时自动匹配相似问题
- [ ] Agent 之间共享公共记忆（避免重复发现同类问题）
