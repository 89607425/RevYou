<div align="right">

🌐 **语言 / Language:** &nbsp; [English](README.md) &nbsp;|&nbsp; **[简体中文](README.zh-CN.md)**

</div>

<div align="center">

<img src="docs/images/logo-banner.png" alt="RevYou — 自主需求审查 Multi-Agent 系统" width="860"/>

<br/>

<p align="center">
  <a href="https://github.com/89607425/RevYou"><img src="https://img.shields.io/badge/版本-1.0.0-6366f1?style=for-the-badge" alt="版本"/></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React 18"/>
  <img src="https://img.shields.io/badge/TypeScript-5-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript"/>
  <img src="https://img.shields.io/badge/DeepSeek-8B5CF6?style=for-the-badge" alt="DeepSeek"/>
  <a href="https://github.com/89607425/RevYou/stargazers"><img src="https://img.shields.io/github/stars/89607425/RevYou?style=for-the-badge&color=6366f1" alt="Stars"/></a>
  <a href="https://github.com/89607425/RevYou/issues"><img src="https://img.shields.io/github/issues/89607425/RevYou?style=for-the-badge" alt="Issues"/></a>
  <img src="https://img.shields.io/badge/PRs-欢迎-22c55e?style=for-the-badge" alt="PRs Welcome"/>
</p>

</div>

---

**RevYou** 是一套**自主多智能体**系统，把产品、开发、测试三位资深评审员摆到每一份需求文档前面。每个 Agent 各自跑一遍 **Plan → Execute → Reflect → Adjust → Consolidate** 五步循环，让审查路径**因文档而异**——而不是写死在代码里。再加一轮跨视角交叉审查，把任何单一视角都可能漏掉的盲区补上。

> ✨ 不同的需求，走出不同的审查路径。没有两次审查长得完全一样。

<br/>

## 📑 目录

- [✨ 核心特性](#-核心特性)
- [🎬 流程一览](#-流程一览)
- [🧠 设计思想](#-设计思想)
- [🏗️ 整体架构](#-整体架构)
- [🔁 Agent 自主五步循环](#-agent-自主五步循环)
- [🧪 两阶段审查](#-两阶段审查)
- [🚀 快速开始](#-快速开始)
- [📂 项目结构](#-项目结构)
- [🌐 API 速查](#-api-速查)
- [🧬 技术栈](#-技术栈)
- [📏 设计原则](#-设计原则)
- [🗺️ 路线图](#-路线图)
- [🤝 参与贡献](#-参与贡献)
- [📄 开源协议](#-开源协议)
- [🙏 致谢](#-致谢)

---

## ✨ 核心特性

- 🧠 **真正的自主规划，不是脚本。** 每个 Agent 先读文档，自己产出 `ReviewPlan`——明确"审什么、怎么审、为什么这样审"——然后才动手。
- 🪞 **自检 + 条件补审。** 每次执行后必走 Reflect 自检；Agent 判定有真实遗漏时再走 Adjust 补审（最多 2 轮、12 次 LLM 调用硬上限）。
- 🧩 **三视角并行 + 交叉。** PM / Dev / Test 先独立审查；再让每个 Agent 盯一遍"另外两个 Agent 漏掉了什么"做定向重审。
- 🧰 **三种输入通道。** 粘贴 Markdown、上传 `.md` / `.pdf` 文件、通过 OpenAPI 直连 TAPD 拉需求。
- 📜 **结构化报告。** 问题按四级严重度分类、统计跨 Agent 认同/异议、给出最终就绪结论，支持导出 MD / JSON。
- 💾 **MySQL 持久化存储。** 每次审查的最终报告、完整思考轨迹和所有中间产物默认全部入库 MySQL（SQLite 可作单机回退），专门的**审查历史**页支持随时回看、重开或删除。
- 📡 **思考轨迹全量可见。** 每一步中间产物（plan / execute / reflect / consolidate）全部落库，并通过 SSE 实时推到浏览器。
- 🛡️ **硬性成本与安全护栏。** Agent 是纯推理单元——不能调工具、不能上网、不能读写文件。所有 I/O 全部由 Orchestrator 兜住。

---

## 🎬 流程一览

```text
  ┌──────────┐    ┌──────────────────┐    ┌────────────────────────┐    ┌─────────────┐
  │ 用户输入 │ →  │ Orchestrator 解析│ →  │ 3 个 Agent 并行执行     │ →  │ 交叉审查    │
  │ MD/PDF/  │    │ 需求并按 token   │    │  (各自：Plan→Exec→     │    │  Phase 2    │
  │ TAPD ID  │    │ 预算切上下文     │    │   Reflect→Adjust→     │    │ (peer-blind)│
  └──────────┘    └──────────────────┘    │   Consolidate)        │    └──────┬──────┘
                                            └────────────────────────┘           │
                                                                                 ▼
                                                                       ┌──────────────────┐
                                                                       │ 聚合后的         │
                                                                       │ 结构化审查报告   │
                                                                       │ + 思考轨迹       │
                                                                       └──────────────────┘
```

### Phase 1 — 三视角并行独立审查

<img src="docs/images/screenshot-phase1-progress.png" alt="RevYou Phase 1：三 Agent 并行" width="860"/>

每个 Agent 独立运行自己的五步循环。不同的需求会自然走出不同的 `ReviewPlan`——审哪里、按什么顺序，全是 Agent 自己拍板。

### Phase 2 — 跨视角交叉审查

<img src="docs/images/screenshot-phase2-cross-review.png" alt="RevYou Phase 2：交叉审查" width="860"/>

Phase 1 结束后，每个 Agent 拿到另外两个 Agent 暴露的盲区，再做一轮定向重审。图中标签从「独立审查」翻成「交叉审查」即代表进入本阶段。

### 最终聚合报告

<img src="docs/images/screenshot-final-report.png" alt="RevYou 最终聚合报告" width="860"/>

Orchestrator 把所有 Agent 的问题去重打分、汇总严重度、列出 Top 风险，并渲染出可一键导出（Markdown / JSON）的最终报告。

---

## 🧠 设计思想

整个系统围绕**职责清晰的三层分离**展开：

| 层              | 职责                                                                                  | 严格不能做的事                           |
|-----------------|---------------------------------------------------------------------------------------|------------------------------------------|
| **前端**        | UI 渲染、用户输入、订阅 SSE 实时轨迹、呈现最终报告                                    | 不能调 LLM、不能调 TAPD、不能持久化任何东西 |
| **Orchestrator** | 文档解析、TAPD OpenAPI 调用、LLM 调用、任务持久化、报告聚合、SSE 事件分发             | 不能生成审查内容、不能做主观判断         |
| **Agent**       | 输入文本，输出结构化 JSON。决定"审什么、怎么审、何时停"                                | 不能读写文件、不能上网、不能调任何工具   |

最后一条是最关键的：**Agent 是纯粹的 LLM 推理单元**——它不能浏览、不能调 TAPD、不能读文件、不能往任何地方写。Orchestrator 把每一次 LLM 调用和每一次副作用都包起来，让 Agent 变得极其容易测试、替换和推理。

---

## 🏗️ 整体架构

<img src="docs/images/architecture.svg" alt="RevYou 三层架构" width="920"/>

- **前端**（React 18 + Vite + Ant Design 5）是薄薄的客户端，只通过 HTTP / SSE 跟 Orchestrator 对话。
- **Orchestrator** 是 FastAPI 进程，**独占**所有外部交互：文档解析、TAPD OpenAPI、LLM 调用、MySQL 持久化、SSE 事件分发、最终报告聚合。
- **Agent** 是三个一模一样的五步循环，每个对应一种角色（PM / Dev / Test）。它们不共享状态、并发执行，只在最后通过报告交换信息。

---

## 🔁 Agent 自主五步循环

<img src="docs/images/agent-loop.svg" alt="RevYou 五步 Agent 循环" width="920"/>

每个 Agent 是一段闭合的五步循环，**每个 phase 跑一次**：

1. **Plan（规划）**——Agent 先读需求，产出一份 `ReviewPlan`：要重点审哪些维度、为什么、按什么顺序。
2. **Execute（执行）**——并行审查每个 focus area，输出带严重度、证据、理由的结构化问题。
3. **Reflect（反思）**——Agent 回头审视自己的产出，追问"我漏掉了什么？"，产出一份 `ReflectionReport`。
4. **Adjust（补审）**——**条件触发**。如果反思发现了真实盲区，Agent 就会对这些点做一次定向重审（最多 2 轮，避免无限循环）。
5. **Consolidate（定稿）**——Agent 去重、评分，产出最终的 per-agent 报告（最多 15 条问题，控制 token 用量）。

一次完整审查通常产生 **30–60 次 LLM 调用**（3 个 Agent × 2 个 phase，每个 phase 约 10 次）。在 DeepSeek 上大概 1–2 分钟跑完。

---

## 🧪 两阶段审查

| 阶段                          | 发生了什么                                                                                  |
|-------------------------------|---------------------------------------------------------------------------------------------|
| **Phase 1 — 独立审查**         | PM / Dev / Test 各自冷启动读需求，跑完完整的五步循环。                                       |
| **Phase 2 — 交叉审查**         | 每个 Agent 拿到"另外两个 Agent 漏掉的点"，做一次定向重审。                                  |
| **聚合**                       | Orchestrator 对问题做模糊去重（标题+证据）、计算跨 Agent 认同度、给 Top 风险打分、产出最终就绪结论。 |

跨 Agent 认同是个强信号：PM 和 Test 同时标记同一个缺口，团队就该认真对待。

---

## 💾 持久化存储

每一次审查——最终报告、完整思考轨迹、所有中间产物——都会写入配置好的存储后端。默认是 **MySQL**（适合多人协作 / 长时间部署），**SQLite** 作为单机回退方案。

```text
┌────────────────────────────────────────────────────────────────────┐
│  MySQL（默认）            SQLite（回退）                           │
│  ──────────────────         ─────────────────                      │
│  • PyMySQL + DBUtils 连接池   • 零配置，文件式                      │
│  • InnoDB / utf8mb4           • 单进程安全                          │
│  • ON DELETE CASCADE          • 强制外键                            │
│  • 支撑并发用户               • 适合本机或单人开发                   │
└────────────────────────────────────────────────────────────────────┘
```

两个后端实现同一个 `SessionStoreBase` 接口，切换只改一行配置（`STORAGE_BACKEND=sqlite`），业务代码完全不用动。

| 环境变量             | 默认值            | 说明                                       |
|----------------------|-------------------|--------------------------------------------|
| `STORAGE_BACKEND`    | `mysql`           | `mysql`（默认）或 `sqlite`（回退）         |
| `MYSQL_HOST`         | `127.0.0.1`       | MySQL 主机                                 |
| `MYSQL_PORT`         | `3306`            | MySQL 端口                                 |
| `MYSQL_USER`         | `root`            | MySQL 用户                                 |
| `MYSQL_PASSWORD`     | *(空)*            | MySQL 密码                                 |
| `MYSQL_DATABASE`     | `revyou_reviews`  | MySQL 数据库名（首次启动自动建）           |
| `MYSQL_POOL_SIZE`    | `5`               | DBUtils 连接池大小                         |
| `DB_PATH`            | `data/review.db`  | SQLite 文件路径（仅在回退模式下生效）      |

表结构首次启动时自动创建。`ON DELETE CASCADE` 外键约束保证删除一个 job 时所有 thinking_steps 一并清理。

> 💡 前端**审查历史**页（`/history`）是查看持久化结果最直观的方式，支持关键词搜索、来源/状态筛选和就地删除。

---

## 🚀 快速开始

### 准备环境

- **Python ≥ 3.10**（Anaconda 或 venv 都行；项目自带 `conda activate revyou` 示例）
- **Node.js ≥ 18**（Vite 前端需要）
- 一个 **DeepSeek API Key**（或任何 OpenAI 兼容端点，通过环境变量配置）
- *(可选)* **TAPD API Token**——只有要用 TAPD 直连时才需要

### 1. 克隆 & 配置

```bash
git clone https://github.com/89607425/RevYou.git
cd RevYou

# 后端
cd backend
cp .env.example .env
# 编辑 .env，填入：
#   LLM_API_KEY=sk-...
#   MYSQL_PASSWORD=...   （或设 STORAGE_BACKEND=sqlite 走 SQLite 回退）
#   TAPD_TOKEN=...            （仅 TAPD 集成需要）
#   TAPD_WORKSPACE_IDS=...    （逗号分隔）
```

### 2. 启动后端

```bash
conda activate revyou        # 或者用你自己的 venv
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API 交互文档：<http://127.0.0.1:8000/docs>

### 3. 启动前端

```bash
cd ../frontend
npm install
npm run dev
```

浏览器打开 <http://localhost:5173>，粘贴或上传需求，看着 Agent 干活即可。

### 4. 跑测试

```bash
cd backend
python -m pytest tests/ -v
```

测试覆盖：文档解析、LLM JSON 抢救、Agent Runner、报告聚合。

---

## 📂 项目结构

```text
RevYou/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI 入口
│   │   ├── config.py                  # Pydantic 配置（加载 .env）
│   │   ├── models/                    # Pydantic 数据模型
│   │   ├── routers/                   # /api/review, /api/jobs, /api/tapd
│   │   ├── services/
│   │   │   ├── agent_runner.py        # ★ 五步自主循环驱动器（核心）
│   │   │   ├── orchestrator.py        # 主流程状态机
│   │   │   ├── doc_parser.py          # Markdown / PDF 解析
│   │   │   ├── llm_client.py          # DeepSeek 客户端 + JSON 抢救
│   │   │   ├── prompt_manager.py      # Prompt 模板加载
│   │   │   ├── context_builder.py     # token 预算内的上下文组装
│   │   │   ├── report_aggregator.py   # 跨 Agent 去重 + 评分
│   │   │   ├── tapd_adapter.py        # TAPD OpenAPI 客户端
│   │   │   └── event_bus.py           # 进程内 SSE 事件总线
│   │   └── storage/                   # 可插拔持久化（MySQL | SQLite）
│   │       ├── base.py                # 存储抽象接口
│   │       ├── mysql_store.py         # MySQL 后端（默认推荐）
│   │       └── sqlite_store.py        # SQLite 回退（单机）
│   ├── prompts/
│   │   ├── phase1/                    # plan / execute / reflect / consolidate
│   │   ├── phase2/                    # 交叉审查 prompt
│   │   └── roles/                     # PM / Dev / Test 领域 prompt
│   └── tests/                         # Pytest 测试集
├── frontend/
│   ├── src/
│   │   ├── pages/                     # 主页、报告页、历史记录页
│   │   ├── components/                # 轨迹查看器、问题卡片
│   │   ├── api/                       # Fetch + SSE 客户端
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   └── images/                        # README 配图 + Logo
├── .env.example                       # 模板——永远不要提交真实 .env
├── .gitignore
├── README.md                          # 英文版（默认）
└── README.zh-CN.md                    # 简体中文版 ← 你在这里
```

---

## 🌐 API 速查

| 端点                                  | 方法   | 说明                                  |
|---------------------------------------|--------|---------------------------------------|
| `/api/review/markdown`                | POST   | 提交 Markdown 文本进行审查            |
| `/api/review/file`                    | POST   | 上传 `.md` / `.pdf` 文件审查          |
| `/api/review/tapd`                    | POST   | 从 TAPD 拉取需求并审查                |
| `/api/jobs`                           | GET    | 列出历史审查（支持 `status` / `source_type` / `keyword` 筛选，分页） |
| `/api/jobs/{job_id}`                  | GET    | 查询任务状态 + 最终报告               |
| `/api/jobs/{job_id}/events`           | GET    | 订阅实时 SSE 轨迹                     |
| `/api/jobs/{job_id}/trace`            | GET    | 回放完整思考轨迹                      |
| `/api/jobs/{job_id}`                  | DELETE | 删除任务（含其全部 thinking steps）   |
| `/api/tapd/stories/search`            | GET    | 按关键字搜索 TAPD 需求                |
| `/api/tapd/stories/fetch`             | POST   | 审查前预览 TAPD 需求                  |

后端启动后，完整 API 文档在 `http://127.0.0.1:8000/docs`。

---

## 🧬 技术栈

**后端**

- 🐍 Python 3.10+ · Pydantic v2
- ⚡ FastAPI + Uvicorn
- 🤖 DeepSeek（OpenAI 兼容 chat completion、JSON 模式、`max_tokens=8192`）
- 🗄️ MySQL 8.0+，通过 `PyMySQL` + `DBUtils` 连接池（SQLite 仍可作为单机回退）
- 📄 `python-markdown` 解析 MD · `PyMuPDF` 解析 PDF
- 🌐 `httpx` 调 TAPD OpenAPI
- 🧪 `pytest` 单元测试

**前端**

- ⚛️ React 18 + TypeScript 5
- ⚡ Vite 5
- 🎨 Ant Design 5
- 🧭 React Router 6
- 📡 原生 `EventSource` 订阅 SSE

> 没有 LangChain、没有 LlamaIndex、没有任何重型的 Agent 框架。五步循环在 `agent_runner.py` 里手写了大约 350 行 Python——一口气能读完。

---

## 📏 设计原则

1. **Agent 是纯推理单元。** 不调工具、不做 I/O、不上网。所有副作用由 Orchestrator 包起来。
2. **自主性有边界。** Agent 决定"审什么、怎么审、何时停"；但不决定工具使用、整体流程编排。
3. **核心小、外延大。** Orchestrator 控制在 ~1000 行内，Agent 循环控制在 ~400 行内。真正难的东西写在 prompt 里，不写在代码里。
4. **本地优先、单用户。** 无认证、无多租户、无云锁定。带上你自己的 API key 就能跑。
5. **Token 友好。** `max_tokens=8192`、温度 0.2、JSON 模式，再加一道 JSON 抢救把截断的输出救回来，而不是直接扔掉。
6. **基础设施故意选"无聊"的。** MySQL + DBUtils 做存储、FastAPI、Vite。真正有意思的是 Agent 循环，不是这些脚手架。

---

## 🗺️ 路线图

- [x] 三 Agent 五步循环 + 反思 + 条件补审
- [x] Phase 2 跨视角交叉审查
- [x] TAPD OpenAPI 集成
- [x] SSE 实时轨迹推送
- [x] 聚合后的结构化报告
- [x] 双语 README（EN / 简体中文）
- [x] MySQL 持久化存储 + 审查历史页
- [ ] **Diff 审查**——审两个版本之间的差异，不只审最新版本
- [ ] **历史质量分**——追踪审查质量随时间的演化
- [ ] **可插拔 LLM 提供商**（OpenAI / Anthropic / 本地 Ollama），每个 provider 单独调优 prompt
- [ ] 完整报告导出为可打印 PDF
- [ ] 多租户模式（可选，通过开关启用）
- [ ] **内联评论锚点**——把每个问题链接到原文档的特定位置

---

## 🤝 参与贡献

非常欢迎 Issue、PR 和新点子。几条保持水准的约定：

1. **保持 Agent 循环小巧。** 如果一个功能要在 `agent_runner.py` 里加超过 ~50 行，它大概率应该放 Orchestrator。
2. **加测试。** `services/` 里能写单测的都应该有。
3. **不要把 I/O 偷偷塞进 Agent。** "Agent 是纯的"这条铁律不能破——它正是让系统可测、可控、可便宜的关键。
4. **改 prompt 是头等大事。** 动了哪个 prompt，就更新对应的角色文档，并跑一遍冒烟审查。

```bash
# 本地开发循环
git checkout -b feature/your-thing
# ...写代码...
cd backend && python -m pytest tests/ -v
git commit -m "feat: 描述改了什么、为什么"
```

---

## 📄 开源协议

本项目以 **MIT 协议**开源——详见 [`LICENSE`](LICENSE)。

> 💡 如果 RevYou 对你有用，给 GitHub 仓库点个 ⭐ 是最简单的感谢方式，也能帮到更多人发现它。

---

## 🙏 致谢

- **DeepSeek**——高质量、低成本的 OpenAI 兼容推理，让一次审查 50 次 LLM 调用也负担得起。
- **TAPD**——干净、好用的 OpenAPI 接口。
- **Ant Design** 团队——让 UI 保持一致性的设计语言。
- 整套技术栈背后的所有开源项目——FastAPI、React、Vite、PyMuPDF、Pydantic，以及那一长串把"周末小 hack"变成"真正能用的工具"的库。

---

<div align="center">

<sub>用 ❤️ 打造，固执地相信：需求值得被认真审一遍，而不是被打勾。</sub>

<br/>

🌐 [English](README.md) &nbsp;|&nbsp; **[简体中文](README.zh-CN.md)**

</div>
