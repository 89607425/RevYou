# RevYou - AI 需求评审 Agent

> 让 AI 代替 PM、Dev、QA 三个角色并行审查你的 PRD 文档，在开发前发现逻辑漏洞、技术风险和测试遗漏。

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)](https://docs.docker.com/compose/)

---

## 功能概述

### 核心能力

- **三 Agent 并行审查**：PM（产品视角）、Dev（技术视角）、QA（测试视角）三个 AI Agent 同时审查 PRD，各司其职
- **两阶段审查模式**：
  - **确定性工作流**：一次性完成审查，适合标准 PRD
  - **自主 Agent 模式**：支持追问和澄清，适合复杂 PRD
- **多格式 PRD 导入**：支持 Markdown 文本、PDF、DOCX 文件上传，以及 TAPD 项目导入
- **图片识别**：自动识别 PRD 中的流程图/架构图，注入文本上下文

### 评审维度

| Agent | 审查维度 |
|-------|---------|
| PM | 用户流程完整性、状态流转、埋点缺失、文案一致性、边界条件、异常流 |
| Dev | 技术风险、接口依赖、数据一致性、幂等设计、并发问题、兼容性 |
| QA | 边界条件测试、异常流程测试、Case 遗漏、状态覆盖 |

### 问题管理

- 问题严重等级：HIGH / MEDIUM / LOW，带置信度
- WebSocket 实时推送审查进度和发现的问题
- 问题状态流转：OPEN → ACKNOWLEDGED → IN_PROGRESS → RESOLVED → CLOSED
- 支持对每个问题进行评论讨论

### 导出与统计

- 审查报告导出：Markdown / PDF
- 问题列表导出：CSV / Excel
- 项目风险仪表盘：问题分布、严重等级统计、趋势分析

---

## 技术架构

```
┌─────────────┐     ┌──────────────────────────────┐
│  Next.js 14 │────▶│  FastAPI (Python 3.11)        │
│  (Port 3000)│     │  /api/v1/*                   │
└─────────────┘     │  /ws/sessions/{id}           │
                    └──────────┬───────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
   │  PostgreSQL  │  │    Redis     │  │  LangGraph       │
   │  (Port 5432) │  │  (Port 6379) │  │  (Agent 引擎)    │
   └──────────────┘  └──────────────┘  └──────────────────┘
```

- **后端**：FastAPI + SQLAlchemy (async) + PostgreSQL 15 + Redis 7
- **前端**：Next.js 14 + TypeScript + Tailwind CSS
- **Agent 引擎**：LangGraph + StateGraph，fan-out/fan-in 并行模式
- **LLM**：通过硅基流动 (SiliconFlow) API 调用 DeepSeek-V3 等模型
- **基础设施**：Docker Compose 编排，支持一键启动

---

## 快速开始

### 前置要求

- [Docker](https://docs.docker.com/get-docker/) 和 Docker Compose
- 硅基流动 [API Key](https://cloud.siliconflow.cn/)（用于 LLM 调用）

### 1. 克隆项目

```bash
git clone https://github.com/your-username/RevYou.git
cd RevYou
```

### 2. 配置环境变量

编辑 `.env` 文件，填入你的硅基流动 API Key：

```bash
LLM_DEEPSEEK_API_KEY=sk-your-key-here
LLM_QWEN_API_KEY=sk-your-key-here
LLM_OPENAI_API_KEY=sk-your-key-here
LLM_BASE_URL=https://api.siliconflow.cn/v1
```

> 💡 如果使用其他 LLM 提供商，修改 `LLM_BASE_URL` 和对应的 `LLM_*_BASE_URL` 即可。所有接口兼容 OpenAI API 格式。

### 3. 一键启动

```bash
docker compose up -d
```

首次启动会拉取镜像并安装依赖，**约需 2-5 分钟**。后续启动只需几秒。

### 4. 访问应用

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:3000 |
| API 文档 (Swagger) | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/api/v1/health |

### 5. 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员 |
| pm | pm123 | 产品经理 |
| dev | dev123 | 开发者 |
| qa | qa123 | 测试工程师 |

### 6. 使用流程

1. **创建项目** → 登录后新建评审项目，可配置 Agent 角色和自定义规则
2. **创建评审会话** → 粘贴 PRD Markdown 文本 / 上传 PDF/DOCX 文件 / 从 TAPD 导入
3. **等待审查完成** → AI Agent 并行审查，WebSocket 实时推送发现的问题
4. **查看结果** → 在评审工作台查看三栏布局（PRD 结构 / 原文 / 问题列表）
5. **处理问题** → 对问题分配状态、添加评论、导出报告

---

## 项目结构

```
RevYou/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API 路由（auth, projects, sessions, issues, dashboard, export, notifications, tapd, ws）
│   │   ├── core/             # 核心配置（config, database, security）
│   │   ├── models/           # 数据模型（user, project, review, notification, audit）
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── services/         # 业务逻辑（agent_engine, prd_parser, tapd_service, websocket_manager）
│   │   ├── scripts/          # 工具脚本（seed.py）
│   │   ├── main.py           # FastAPI 入口
│   │   └── worker.py         # 后台 Worker 进程
│   ├── sql/init.sql          # 数据库初始化 DDL（9 张表）
│   ├── alembic/              # 数据库迁移
│   ├── requirements.txt      # Python 依赖
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js 页面路由
│   │   │   ├── login/        # 登录页
│   │   │   ├── projects/     # 项目列表 & 会话管理
│   │   │   └── sessions/[id] # 评审工作台
│   │   ├── components/       # 共享组件
│   │   ├── hooks/            # 自定义 Hooks
│   │   ├── lib/              # API 客户端
│   │   └── types/            # TypeScript 类型定义
│   └── Dockerfile
├── docker-compose.yml        # Docker 编排（web, api, worker, postgres, redis）
├── .env                      # 环境变量
└── README.md
```

---

## 常见问题

### Docker 首次启动为什么慢？

首次 `docker compose up -d` 需要：
1. 拉取基础镜像（Python、PostgreSQL、Redis）
2. 下载并编译 Python 依赖（约 60 个包）
3. 构建前端 Next.js 应用

**后续启动只需几秒**，Docker 会缓存所有构建层。只有修改 `requirements.txt` 或 `Dockerfile` 时才需要重新构建。

### 如何停止服务？

```bash
docker compose down        # 停止并移除容器
docker compose down -v     # 同时删除数据卷（数据库数据会丢失）
```

### 如何查看日志？

```bash
docker compose logs -f api      # API 日志
docker compose logs -f worker   # Worker 日志
docker compose logs -f web      # 前端日志
```

### 如何重置数据库？

```bash
docker compose down -v
docker compose up -d
docker compose exec api python -m app.scripts.seed
```

---

## License

MIT
# RevYou
# RevYou
