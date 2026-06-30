# PRD 缺口 TODO 清单

## 当前实现 vs PRD V1.1 最终完整版 差距分析

> 更新时间：2026-06-11
> 状态说明：✅ 已完成 | 🔶 部分完成 | ❌ 未实现 | ⬜ Phase 2（MVP 不做）

---

## 一、P0 核心功能缺口（MVP 必须）

### 1.1 自主 Agent 模式（AUTONOMOUS）🔶

| 需求 (PRD 5.2) | 当前状态 | 缺口 |
|---|---|---|
| Agent 主动追问（最大 5 次） | 🔶 Agent 可生成 `follow_up_questions`，存入 JSONB | 追问→暂停→等待用户回复→恢复审查的完整 Human-in-the-loop 机制未实现。LangGraph `interrupt` 机制未接入 |
| 用户回复追问（PRD 5.2: ANSWER/SKIP/DOWNGRADE） | 🔶 WebSocket 有 `FOLLOW_UP_ANSWER` 消息类型 | `ws_manager.handle_follow_up_answer()` 是空壳，不保存回复、不恢复图执行、不触发追加审查 |
| 自主模式前端 UI（追问面板） | ❌ | `sessions/[id]/page.tsx` 有 `FollowUp` 接口和状态变量，但追问面板 JSX **未渲染**，回复 Modal 未显示 |
| 追加审查轮次（最大 3 轮） | ❌ | 自主模式图 `build_autonomous_graph()` 直接委托给 `build_deterministic_graph()` |
| 模式选择规则（PRD 5.3: >5 HIGH 自动提示切换） | ❌ | 无自动提示逻辑 |

### 1.2 图片识别/多模态审查 ❌

| 需求 (PRD 7.2, 4.2 Step 1) | 当前状态 | 缺口 |
|---|---|---|
| 图片内容识别（流程图、原型图、架构图） | ❌ | `prd_parser.py` 有 `enrich_prd_with_image_text()` 和 `recognize_image()` 函数，但 **未被任何 API 调用**。Agent 审查时不会对图片调用多模态模型 |
| 多模态模型自动切换 | ❌ | `config` 中有 `multimodal_model: "qwen-vl-max"`，但 agent_engine 硬编码用 `ChatOpenAI` 做纯文本调用，不检测图片、不切换模型 |
| 图片上传（PNG/JPG） | ❌ | `/sessions/upload` 仅支持 PDF/DOCX，不支持纯图片上传 |
| TAPD 附件图片识别 | ❌ | `tapd_service.py` 有 `get_attachments()`，但 `compose_full_prd()` 仅列出附件名，不下载图片、不调多模态模型 |

### 1.3 审查报告导出 🔶

| 需求 (PRD 4.6, 技术补充 1.7) | 当前状态 | 缺口 |
|---|---|---|
| Markdown 报告导出 | ✅ | `GET /export/report?format=markdown` 已实现 |
| PDF 报告导出 | 🔶 | 接口返回 `StreamingResponse` 但仅 `media_type="text/plain"`，不生成真正的 PDF |
| Excel/CSV 问题清单导出 | ✅ | `GET /export/issues?format=csv\|xlsx` 已实现（使用 openpyxl） |
| 一键复制（单条问题） | ✅ | `GET /issues/{id}/copy` + 剪贴板 已实现 |
| **前端导出页面** | ❌ | `frontend/src/app/export/` 目录为空。session 页面的"导出报告"按钮无点击事件 |

### 1.4 TAPD 只读集成 🔶

| 需求 (PRD 6.1) | 当前状态 | 缺口 |
|---|---|---|
| 拉取需求详情 | ✅ | `get_story()` 已实现 |
| 拉取附件 | ✅ | `get_attachments()` 已实现 |
| 拉取评论 | ✅ | `get_comments()` 已实现 |
| 拉取关联缺陷 | ✅ | `get_bugs()` 已实现 |
| 拉取迭代信息 | ✅ | `get_iterations()` 已实现 |
| 拉取项目成员 | ❌ | 未实现 `GET /workspaces/users` |
| 拉取需求变更历史 | ✅ | `get_story_changes()` 已实现 |
| 拉取 Wiki | ✅ | `get_wikis()` 已实现 |
| 拉取 Tasks | ✅ | `get_tasks()` 已实现 |
| compose_full_prd() 合成完整 PRD | ✅ | 已实现，含 Markdown 格式的 Story + 子需求 + Tasks + Bugs + Wiki + 评论 + 变更历史 |
| **TAPD Token 验证后选项目** | 🔶 | `validate_token()` 返回 workspaces 列表，但前端未实现"选择 workspace"交互 |
| **TAPD 需求搜索 UI** | 🔶 | 后端有 `/tapd/stories/search`，前端创建对话框仅支持手动输入 Story ID，不支持关键词搜索 |

---

## 二、P1 功能缺口（MVP 应完成）

### 2.1 风险仪表盘 🔶

| 需求 (PRD 4.4, 技术补充 1.9) | 当前状态 | 缺口 |
|---|---|---|
| 后端 API | ✅ | `GET /projects/{project_id}/risk-dashboard?period=7d\|30d` 已实现 |
| **前端页面** | ❌ | `frontend/src/app/dashboard/` 目录不存在，导航栏有链接但 404 |
| 趋势数据 | 🔶 | `trend` 字段始终返回空数组 `[]`，未实现时间序列统计 |

### 2.2 问题评论/协作 🔶

| 需求 (PRD 10.1: Dev/QA 回复问题) | 当前状态 | 缺口 |
|---|---|---|
| 后端 API | ✅ | `POST/GET /issues/{id}/comments` 已实现 |
| **前端评论 UI** | ❌ | 问题卡片上无评论展示和输入框 |

### 2.3 问题操作 🔶

| 需求 (PRD 4.5) | 当前状态 | 缺口 |
|---|---|---|
| 确认/标记误报/关闭 | ✅ | 已实现 |
| 调整严重等级 | ✅ | `PATCH /issues/{id}/severity` 已实现 |
| **前端等级调整 UI** | ❌ | 前端无调整严重等级的入口 |
| 重新审查（指定 Agent + 章节） | ❌ | 技术补充定义了 `POST /sessions/{id}/re-review`，但后端未实现该端点 |
| 增量审查（仅改动的章节） | ❌ | PRD 列为 P2，当前从未实现 |

### 2.4 站内通知 🔶

| 需求 (PRD 9.1) | 当前状态 | 缺口 |
|---|---|---|
| 后端 API | ✅ | `GET /notifications`, `PATCH /read`, `PATCH /read-all` 已实现 |
| **通知触发逻辑** | ❌ | `create_notification()` 工具函数存在但**从未被调用**。审查完成、超时、追问等场景都不生成通知 |
| **前端通知页面** | ❌ | `frontend/src/app/notifications/` 目录不存在，无通知铃铛/Badge |
| TAPD Token 过期通知 | ❌ | 未实现 |

### 2.5 权限控制 🔶

| 需求 (PRD 10.1) | 当前状态 | 缺口 |
|---|---|---|
| 角色定义 (PM/Dev/QA/SM/Admin) | ✅ | 模型已定义 |
| 项目成员管理 | ✅ | `ProjectMember` 表 + 查询 |
| **路由级权限校验** | 🔶 | 仅 `get_current_user` 做登录校验，部分管理员接口检查 `role == "ADMIN"`，但 Dev/QA/PM 的功能级权限（如 Dev 不能标记误报）未校验 |
| **前端按钮权限控制** | ❌ | 前端所有操作按钮对所有角色可见可点击 |

### 2.6 新用户引导 ❌

| 需求 (PRD 11) | 当前状态 | 缺口 |
|---|---|---|
| 首次使用引导流程 | ❌ | 完全未实现，计划 Phase 2（P2） |
| TAPD Token 配置引导 | ❌ | 项目设置页有此功能，但无引导 |

---

## 三、严重 Bug 与技术债务

### 3.1 prd_parser 签名不匹配 🐛

| 文件 | 问题 | 影响 |
|---|---|---|
| `sessions.py:251` | `parse_pdf(content, file.filename)` 传入了 `bytes` | **`/sessions/upload` 接口会运行时崩溃** |
| `sessions.py:253` | `parse_docx(content, file.filename)` 传入了 `bytes` | 同上 |
| `prd_parser.py` | `parse_pdf(file_path: str)` 期望文件路径 | `fitz.open(file_path)` 打开 bytes 会报错 |

### 3.2 数据库表创建方式 🐛

- 无 `Base.metadata.create_all()` 调用
- 无 Alembic 迁移配置
- DDL 通过 `backend/sql/init.sql` 手动管理，但该 SQL 文件**未随模型更新而更新**（缺少 `issue_comments`, `notifications`, `audit_logs` 表）

### 3.3 自主模式图未实现 🐛

- `build_autonomous_graph()` 直接 return `build_deterministic_graph()`
- 无 `check_follow` 节点、`human_in_loop` 节点、`re_review` 节点
- 技术补充文档 9.3 节有完整的图结构设计，但零实现

### 3.4 WebSocket 追问回答是空壳 🐛

- `ws_manager.handle_follow_up_answer()` 仅返回 `{"status": "received"}`
- 不保存到数据库、不更新 session.follow_up_questions、不恢复 LangGraph 执行

---

## 四、Phase 2 规划项（MVP 不做）

| 需求 | PRD 章节 | 说明 |
|---|---|---|
| TAPD 写操作（创建工单/同步状态） | 6.2 | 需先申请 TAPD 写权限 |
| 工单状态双向同步 | 6.2 | 依赖写权限 |
| Data Review Agent | 4.3 | 数据埋点审查 |
| 历史需求学习 | 6.3 | TAPD 历史缺陷模式学习 |
| 增量审查 | 4.5 | 仅对修改章节重审 |
| 企业知识库 RAG | 19 | 长期记忆与知识检索 |
| SSO 登录 | 10.2 | SAML2.0/OIDC |
| 多 Agent 协同自治 | 21 | Agent 间自主协商 |
| AI 测试 Case 生成 | 21 | 完整测试用例导出 |
| 多语言 PRD 支持 | 19 | 英文/日文 |
| 审查模板市场 | 21 | 行业审查规则模板 |

---

## 五、优先级排序建议

### 第一批（本周内）：修复阻塞性 Bug

| # | 任务 | 工作量 | 影响范围 |
|---|---|---|---|
| 1 | 修复 `prd_parser.parse_pdf/parse_docx` 支持 bytes 输入 | 1h | FILE 上传功能不可用 |
| 2 | 更新 `init.sql` 补全 `issue_comments`, `notifications`, `audit_logs` 表 | 0.5h | 新表缺失 |
| 3 | 前端导出按钮接上导出 API | 1h | 导出功能不可用 |

### 第二批（1-2 天）：完善 P0 核心功能

| # | 任务 | 工作量 |
|---|---|---|
| 4 | 实现自主模式完整的 Human-in-the-loop 流程（追问→暂停→回复→恢复） | 1d |
| 5 | 实现图片识别/多模态审查（TAPD 附件下载 + 多模态模型调用） | 1d |
| 6 | 前端追问面板 UI（右侧栏追问卡片 + 回复 Modal） | 0.5d |

### 第三批（1-2 天）：补全 P1 功能

| # | 任务 | 工作量 |
|---|---|---|
| 7 | 前端风险仪表盘页面 | 1d |
| 8 | 前端通知页面 + 铃铛 Badge + 通知触发逻辑 | 1d |
| 9 | 前端问题评论 UI | 0.5d |
| 10 | 前端等级调整 UI + 重新审查端点 | 0.5d |
| 11 | 路由级和前端按钮权限控制 | 0.5d |

### 第四批（1 天）：体验优化

| # | 任务 | 工作量 |
|---|---|---|
| 12 | PDF 报告真正生成 PDF（`reportlab` 或 `weasyprint`） | 0.5d |
| 13 | TAPD 需求搜索 UI（关键词搜索 + Story 选择器） | 0.5d |
| 14 | 修复趋势数据计算 | 0.5h |
