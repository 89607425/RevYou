# AI需求评审Agent — 技术补充文档

> **关联PRD**：AI需求评审Agent-PRD-V1.1  
> **文档版本**：V1.1  
> **编写日期**：2026-06-11  
> **文档性质**：PRD技术附录，与PRD V1.1配套使用

---

## 修订记录

| 版本 | 日期 | 修订人 | 修订内容 |
|------|------|--------|----------|
| V1.0 | 2026-06-11 | [待填] | 初版，补齐6项开发阻塞信息 |
| V1.1 | 2026-06-11 | [待填] | 新增4项技术规范：Agent JSON解析策略、文件存储方案、LangGraph图结构、MVP部署环境 |

---

## 一、REST API 接口设计

### 1.1 概述

- **Base URL**：`/api/v1`
- **认证方式**：Bearer Token（本平台JWT），Header: `Authorization: Bearer <token>`
- **通用响应格式**：

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

- **错误码规范**：

| 错误码 | 含义 |
|--------|------|
| 0 | 成功 |
| 1001 | 参数校验失败 |
| 1002 | 未认证 |
| 1003 | 无权限 |
| 2001 | 资源不存在 |
| 2002 | 资源已存在 |
| 3001 | Agent执行失败 |
| 3002 | Agent执行超时 |
| 3003 | AI模型调用失败 |
| 4001 | TAPD Token无效 |
| 4002 | TAPD API调用失败 |
| 5001 | 文件格式不支持 |
| 5002 | 文件大小超限 |

---

### 1.2 认证 API

#### POST /auth/login

登录获取JWT。

**Request**：
```json
{
  "username": "string",
  "password": "string"
}
```

**Response**：
```json
{
  "code": 0,
  "data": {
    "token": "eyJhbGciOi...",
    "expires_at": "2026-06-12T10:00:00Z",
    "user": {
      "user_id": "USR-001",
      "username": "zhangsan",
      "display_name": "张三",
      "role": "PM"
    }
  }
}
```

#### POST /auth/refresh

刷新Token。

**Request**：
```json
{
  "token": "string"
}
```

**Response**：同 login。

---

### 1.3 项目 API

#### GET /projects

获取用户可访问的项目列表。

**Query参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认1 |
| page_size | int | 否 | 每页条数，默认20 |

**Response**：
```json
{
  "code": 0,
  "data": {
    "total": 5,
    "items": [
      {
        "project_id": "PRJ-001",
        "name": "电商平台",
        "tapd_project_id": "12345678",
        "has_tapd_token": true,
        "session_count": 12,
        "member_count": 8,
        "created_at": "2026-06-01T10:00:00Z"
      }
    ]
  }
}
```

#### GET /projects/{project_id}

获取项目详情。

**Response**：
```json
{
  "code": 0,
  "data": {
    "project_id": "PRJ-001",
    "name": "电商平台",
    "tapd_project_id": "12345678",
    "has_tapd_token": true,
    "config": {
      "text_model": "deepseek-v3",
      "multimodal_model": "qwen-vl-max",
      "auto_switch_model": true,
      "confidence_threshold_low": 0.5,
      "confidence_threshold_high": 0.8,
      "max_review_rounds_deterministic": 1,
      "max_review_rounds_autonomous": 3,
      "max_follow_up_questions": 5
    },
    "members": [
      { "user_id": "USR-001", "display_name": "张三", "role": "PM" }
    ],
    "created_at": "2026-06-01T10:00:00Z"
  }
}
```

#### PUT /projects/{project_id}/config

更新项目Agent配置（仅管理员）。

**Request**：
```json
{
  "text_model": "deepseek-v3",
  "multimodal_model": "qwen-vl-max",
  "auto_switch_model": true,
  "confidence_threshold_low": 0.5,
  "confidence_threshold_high": 0.8,
  "max_review_rounds_deterministic": 1,
  "max_review_rounds_autonomous": 3,
  "max_follow_up_questions": 5
}
```

**Response**：返回更新后的完整项目详情（同 GET /projects/{project_id}）。

#### PUT /projects/{project_id}/tapd-token

配置TAPD API Token（仅管理员）。

**Request**：
```json
{
  "tapd_token": "xxxxxxxxxxxxxxxx"
}
```

**Response**：
```json
{
  "code": 0,
  "data": {
    "valid": true,
    "tapd_project_id": "12345678",
    "message": "Token验证成功，关联TAPD项目：电商平台"
  }
}
```

---

### 1.4 审查会话 API

#### POST /sessions

创建审查会话。

**Request**（multipart/form-data）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_id | string | 是 | 项目ID |
| agent_mode | string | 是 | `DETERMINISTIC` / `AUTONOMOUS` |
| prd_source | string | 是 | `TEXT` / `FILE` / `TAPD` |
| prd_text | string | 条件必填 | prd_source=TEXT时必填，PRD文本内容 |
| prd_files | file[] | 条件必填 | prd_source=FILE时必填，支持多文件上传 |
| tapd_story_id | string | 条件必填 | prd_source=TAPD时必填，TAPD需求ID |

**Response**：
```json
{
  "code": 0,
  "data": {
    "session_id": "SES-20260611-001",
    "project_id": "PRJ-001",
    "status": "RUNNING",
    "agent_mode": "AUTONOMOUS",
    "prd_source": "FILE",
    "prd_structure": {
      "sections": [
        {
          "section_id": "S1",
          "title": "一、项目背景",
          "level": 1,
          "children": [
            { "section_id": "S1.1", "title": "1.1 行业现状", "level": 2, "children": [] }
          ]
        }
      ],
      "total_sections": 15,
      "total_chars": 8500
    },
    "prd_images": [
      {
        "image_id": "IMG-001",
        "filename": "flow.png",
        "source": "TAPD_ATTACHMENT",
        "recognition_status": "PROCESSING",
        "recognition_result": null
      }
    ],
    "tapd_story_id": null,
    "initiator_id": "USR-001",
    "created_at": "2026-06-11T10:00:00Z",
    "estimated_completion": "2026-06-11T10:05:00Z"
  }
}
```

#### GET /sessions

获取审查会话列表。

**Query参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_id | string | 是 | 项目ID |
| status | string | 否 | 过滤状态：RUNNING/COMPLETED/TIMEOUT/CANCELLED |
| page | int | 否 | 页码，默认1 |
| page_size | int | 否 | 每页条数，默认20 |

**Response**：
```json
{
  "code": 0,
  "data": {
    "total": 8,
    "items": [
      {
        "session_id": "SES-20260611-001",
        "project_id": "PRJ-001",
        "status": "COMPLETED",
        "agent_mode": "AUTONOMOUS",
        "prd_source": "FILE",
        "issue_count": { "HIGH": 2, "MEDIUM": 5, "LOW": 3, "total": 10 },
        "initiator": { "user_id": "USR-001", "display_name": "张三" },
        "created_at": "2026-06-11T10:00:00Z",
        "completed_at": "2026-06-11T10:08:00Z"
      }
    ]
  }
}
```

#### GET /sessions/{session_id}

获取审查会话详情（含审查进度）。

**Response**：
```json
{
  "code": 0,
  "data": {
    "session_id": "SES-20260611-001",
    "project_id": "PRJ-001",
    "status": "RUNNING",
    "agent_mode": "AUTONOMOUS",
    "prd_source": "FILE",
    "prd_structure": { "...": "..." },
    "tapd_story_id": null,
    "initiator_id": "USR-001",
    "agent_progress": [
      {
        "agent": "PM_REVIEW",
        "status": "COMPLETED",
        "round": 1,
        "issue_count": 4,
        "started_at": "2026-06-11T10:00:05Z",
        "completed_at": "2026-06-11T10:01:30Z"
      },
      {
        "agent": "DEV_REVIEW",
        "status": "RUNNING",
        "round": 1,
        "issue_count": 0,
        "started_at": "2026-06-11T10:00:05Z",
        "completed_at": null
      },
      {
        "agent": "QA_REVIEW",
        "status": "PENDING",
        "round": 0,
        "issue_count": 0,
        "started_at": null,
        "completed_at": null
      }
    ],
    "follow_up_questions": [],
    "created_at": "2026-06-11T10:00:00Z",
    "completed_at": null
  }
}
```

#### POST /sessions/{session_id}/cancel

终止审查会话。

**Request**：无请求体。

**Response**：
```json
{
  "code": 0,
  "data": {
    "session_id": "SES-20260611-001",
    "status": "CANCELLED",
    "partial_results_available": true,
    "issue_count": 6
  }
}
```

#### POST /sessions/{session_id}/re-review

重新审查（指定Agent和章节）。

**Request**：
```json
{
  "agent": "PM_REVIEW",
  "section_ids": ["S1.1", "S2.3"],
  "mode": "FULL"
}
```

| 字段 | 说明 |
|------|------|
| agent | 指定Agent：`PM_REVIEW` / `DEV_REVIEW` / `QA_REVIEW` / `ALL` |
| section_ids | 指定重新审查的章节ID列表，为空则全量重审 |
| mode | `FULL`：全量重审 / `INCREMENTAL`：增量审查（MVP仅支持FULL） |

**Response**：同 POST /sessions。

---

### 1.5 审查问题 API

#### GET /sessions/{session_id}/issues

获取审查问题列表。

**Query参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_agent | string | 否 | 过滤Agent：PM_REVIEW/DEV_REVIEW/QA_REVIEW |
| severity | string | 否 | 过滤严重等级：HIGH/MEDIUM/LOW |
| issue_type | string | 否 | 过滤问题类型 |
| status | string | 否 | 过滤状态：OPEN/CONFIRMED/FALSE_POSITIVE/RESOLVED/DEFERRED |
| confidence_min | float | 否 | 最小置信度，默认0.0 |
| section_id | string | 否 | 过滤PRD章节 |
| page | int | 否 | 页码，默认1 |
| page_size | int | 否 | 每页条数，默认50 |
| sort_by | string | 否 | 排序字段：severity/confidence/created_at，默认severity |
| sort_order | string | 否 | asc/desc，默认desc（severity: desc=HIGH优先） |

**Response**：
```json
{
  "code": 0,
  "data": {
    "total": 10,
    "items": [
      {
        "issue_id": "ISS-20260611-001",
        "session_id": "SES-20260611-001",
        "source_agent": "PM_REVIEW",
        "issue_type": "LOGIC_GAP",
        "severity": "HIGH",
        "title": "支付流程缺少幂等设计",
        "description": "PRD第3章'支付流程'中未定义重复提交的处理逻辑，可能导致用户重复扣款...",
        "suggestion": "建议在支付请求中增加幂等Token机制，服务端对相同Token的请求返回相同结果",
        "prd_section": "三、核心业务流程 > 3.2 支付流程",
        "prd_quote": "用户点击'确认支付'后，系统调用支付接口...",
        "image_ref": null,
        "confidence": 0.92,
        "confidence_label": "HIGH",
        "status": "OPEN",
        "created_at": "2026-06-11T10:01:30Z",
        "updated_at": "2026-06-11T10:01:30Z"
      }
    ]
  }
}
```

#### PATCH /sessions/{session_id}/issues/{issue_id}

更新审查问题状态。

**Request**：
```json
{
  "status": "CONFIRMED",
  "resolution_note": "已确认，需要在下一版补充幂等设计"
}
```

| status值 | 必填额外字段 |
|----------|------------|
| CONFIRMED | 无 |
| FALSE_POSITIVE | resolution_note（误报原因，必填） |
| RESOLVED | resolution_note（解决说明，必填） |
| DEFERRED | resolution_note（延期原因，必填） |
| OPEN | 无（重置为OPEN） |

**Response**：返回更新后的完整问题对象。

#### PATCH /sessions/{session_id}/issues/{issue_id}/severity

调整严重等级。

**Request**：
```json
{
  "severity": "MEDIUM",
  "reason": "经评估不属于线上事故级别，调整为中"
}
```

#### POST /sessions/{session_id}/issues/{issue_id}/comments

回复问题（补充信息/解决方案）。

**Request**：
```json
{
  "content": "技术方案：采用Redis分布式锁+幂等Token方案，详见设计文档链接"
}
```

**Response**：
```json
{
  "code": 0,
  "data": {
    "comment_id": "CMT-001",
    "issue_id": "ISS-20260611-001",
    "user_id": "USR-002",
    "content": "技术方案：采用Redis分布式锁+幂等Token方案，详见设计文档链接",
    "created_at": "2026-06-11T11:00:00Z"
  }
}
```

#### GET /sessions/{session_id}/issues/{issue_id}/comments

获取问题评论列表。

**Response**：
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "comment_id": "CMT-001",
        "user_id": "USR-002",
        "display_name": "李四",
        "role": "DEV",
        "content": "技术方案：采用Redis分布式锁+幂等Token方案",
        "created_at": "2026-06-11T11:00:00Z"
      }
    ]
  }
}
```

---

### 1.6 自主模式追问 API

#### GET /sessions/{session_id}/follow-ups

获取追问列表。

**Response**：
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "follow_up_id": "FU-001",
        "session_id": "SES-20260611-001",
        "source_agent": "PM_REVIEW",
        "question": "PRD第3章'支付流程'未定义支付超时后的处理逻辑，请补充说明：1) 超时时间阈值是多少？2) 超时后是自动取消还是允许重试？",
        "prd_section": "三、核心业务流程 > 3.2 支付流程",
        "status": "PENDING",
        "round": 1,
        "created_at": "2026-06-11T10:02:00Z",
        "answered_at": null,
        "answer": null
      }
    ],
    "total_count": 1,
    "pending_count": 1,
    "max_follow_ups": 5
  }
}
```

#### POST /sessions/{session_id}/follow-ups/{follow_up_id}/answer

用户回复追问。

**Request**：
```json
{
  "action": "ANSWER",
  "answer": "支付超时阈值为30秒，超时后自动取消订单并释放库存，用户可重新下单。"
}
```

| action值 | answer字段 | 说明 |
|----------|-----------|------|
| ANSWER | 必填 | 用户补充信息，Agent继续审查 |
| SKIP | 可选 | 跳过追问，Agent标记为"信息不足" |
| DOWNGRADE | 可选 | 终止自主模式，降级为确定性工作流 |

**Response**：
```json
{
  "code": 0,
  "data": {
    "follow_up_id": "FU-001",
    "status": "ANSWERED",
    "agent_continuing": true,
    "remaining_follow_ups": 4
  }
}
```

---

### 1.7 导出 API

#### GET /sessions/{session_id}/export/report

导出审查报告（Markdown/PDF）。

**Query参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| format | string | 是 | `markdown` / `pdf` |
| include_low_confidence | bool | 否 | 是否包含低置信度问题，默认false |
| severity_filter | string | 否 | 过滤等级，逗号分隔，如 `HIGH,MEDIUM` |

**Response**：文件流（Content-Disposition: attachment）。

#### GET /sessions/{session_id}/export/issues

导出问题清单（Excel/CSV）。

**Query参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| format | string | 是 | `xlsx` / `csv` |
| include_low_confidence | bool | 否 | 是否包含低置信度问题，默认false |
| severity_filter | string | 否 | 过滤等级 |

**Response**：文件流。

#### GET /sessions/{session_id}/issues/{issue_id}/copy

获取单条问题的复制文本（格式适配TAPD工单）。

**Response**：
```json
{
  "code": 0,
  "data": {
    "copy_text": "【AI审查】支付流程缺少幂等设计\n\n问题描述：PRD第3章'支付流程'中未定义重复提交的处理逻辑，可能导致用户重复扣款\n\n建议方案：建议在支付请求中增加幂等Token机制，服务端对相同Token的请求返回相同结果\n\n严重等级：HIGH | 置信度：0.92 | 来源：PM Review Agent"
  }
}
```

---

### 1.8 TAPD只读 API

#### GET /tapd/validate-token

验证TAPD Token连通性。

**Response**：
```json
{
  "code": 0,
  "data": {
    "valid": true,
    "project_name": "电商平台",
    "tapd_project_id": "12345678"
  }
}
```

#### GET /tapd/stories/search

搜索TAPD需求单（用于导入时的搜索）。

**Query参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 否 | 关键词搜索 |
| story_id | string | 否 | 精确匹配Story ID |
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页条数，默认10 |

**Response**：
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "story_id": "10001",
        "title": "用户注册流程优化",
        "status": "developing",
        "owner": "张三",
        "has_attachments": true,
        "attachment_count": 2
      }
    ]
  }
}
```

#### GET /tapd/stories/{story_id}/attachments

获取TAPD需求附件列表。

**Response**：
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "attachment_id": "ATT-001",
        "filename": "user_flow.png",
        "filesize": 256000,
        "content_type": "image/png",
        "download_url": "https://..."
      }
    ]
  }
}
```

---

### 1.9 风险面板 API

#### GET /projects/{project_id}/risk-dashboard

获取项目风险面板数据。

**Query参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| period | string | 否 | 统计周期：`7d` / `30d` / `all`，默认30d |

**Response**：
```json
{
  "code": 0,
  "data": {
    "summary": {
      "total_sessions": 25,
      "total_issues": 180,
      "open_issues": 42,
      "high_severity_open": 5,
      "avg_issues_per_session": 7.2
    },
    "severity_distribution": {
      "HIGH": 18,
      "MEDIUM": 82,
      "LOW": 80
    },
    "issue_type_distribution": {
      "TECHNICAL_RISK": 35,
      "LOGIC_GAP": 68,
      "TEST_MISSING": 52,
      "DATA_INCONSISTENCY": 25
    },
    "agent_issue_distribution": {
      "PM_REVIEW": 62,
      "DEV_REVIEW": 58,
      "QA_REVIEW": 60
    },
    "trend": [
      { "date": "2026-05-12", "issues": 8, "high_issues": 1 },
      { "date": "2026-05-19", "issues": 12, "high_issues": 2 }
    ],
    "recent_high_severity": [
      {
        "issue_id": "ISS-xxx",
        "title": "支付流程缺少幂等设计",
        "session_id": "SES-xxx",
        "status": "OPEN",
        "created_at": "2026-06-10T14:00:00Z"
      }
    ]
  }
}
```

---

### 1.10 站内通知 API

#### GET /notifications

获取通知列表。

**Query参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| read | bool | 否 | 过滤已读/未读 |
| type | string | 否 | 通知类型：SESSION_COMPLETED/FOLLOW_UP/SESSION_TIMEOUT/TOKEN_EXPIRED |
| page | int | 否 | 页码 |
| page_size | int | 否 | 默认20 |

#### PATCH /notifications/{notification_id}/read

标记通知为已读。

#### PATCH /notifications/read-all

标记所有通知为已读。

---

## 二、前端页面结构与路由设计

### 2.1 页面清单与路由

| # | 页面名称 | 路由 | 说明 | 权限 |
|---|---------|------|------|------|
| 1 | 登录页 | `/login` | 账号密码登录 | 公开 |
| 2 | 项目列表页 | `/projects` | 用户可访问的项目列表 | 已登录 |
| 3 | 项目设置页 | `/projects/[id]/settings` | TAPD Token配置、Agent规则配置、成员管理 | Admin |
| 4 | 审查会话列表页 | `/projects/[id]/sessions` | 该项目下的审查会话列表 | 已登录 |
| 5 | **审查工作台** | `/sessions/[id]` | **核心页面**：PRD内容+问题列表+追问交互 | 已登录 |
| 6 | 风险仪表盘 | `/projects/[id]/dashboard` | 项目级风险统计面板 | 已登录 |
| 7 | 报告导出页 | `/sessions/[id]/export` | 选择导出格式和过滤条件 | 已登录 |

### 2.2 审查工作台布局（核心页面）

审查工作台是用户使用频率最高的页面，采用**三栏布局**：

```
┌─────────────────────────────────────────────────────────────────────┐
│  顶部导航栏                                                          │
│  [项目名] > [会话名]  │  状态: 审查中  │  [终止审查] [重新审查] [导出]  │
├──────────────┬──────────────────────────────┬───────────────────────┤
│              │                              │                       │
│  左侧栏      │     中间主区域                │    右侧栏              │
│  (240px)     │     (flex-1)                 │    (380px)            │
│              │                              │                       │
│  ┌────────┐  │  ┌────────────────────────┐  │  ┌─────────────────┐  │
│  │PRD目录  │  │  │ PRD内容区               │  │  │ 问题列表面板     │  │
│  │        │  │  │                        │  │  │                 │  │
│  │一、背景 │  │  │ [Markdown渲染的PRD      │  │  │ [按Agent/等级   │  │
│  │二、定位 │  │  │  全文内容，可滚动]       │  │  │  分组的问题卡片] │  │
│  │三、用户 │  │  │                        │  │  │                 │  │
│  │四、流程 │  │  │ 点击某章节时，右侧       │  │  │ 每个卡片：       │  │
│  │ ...    │  │  │ 自动过滤该章节问题       │  │  │ · 等级标签       │  │
│  │        │  │  │                        │  │  │ · 标题           │  │
│  └────────┘  │  │ 选中文字时，可右键       │  │  │ · 置信度标记     │  │
│              │  │ "针对选中内容提问"        │  │  │ · 来源Agent     │  │
│  ┌────────┐  │  │                        │  │  │ · 操作按钮       │  │
│  │Agent   │  │  └────────────────────────┘  │  │  [确认][误报]    │  │
│  │状态    │  │                              │  └─────────────────┘  │
│  │        │  │                              │                       │
│  │🟢PM 4 │  │                              │  ┌─────────────────┐  │
│  │🔴DEV -│  │                              │  │ 追问面板         │  │
│  │🟡QA - │  │                              │  │ (自主模式时展示) │  │
│  └────────┘  │                              │  │                 │  │
│              │                              │  │ 待回复追问列表   │  │
│              │                              │  │ [回复][跳过]     │  │
│              │                              │  │ [降级为确定性]   │  │
│              │                              │  └─────────────────┘  │
├──────────────┴──────────────────────────────┴───────────────────────┤
│  底部状态栏：审查进度 | Agent完成情况 | 耗时                         │
└─────────────────────────────────────────────────────────────────────┘
```

**三栏职责**：

| 区域 | 职责 | 核心交互 |
|------|------|---------|
| 左侧栏 | PRD目录导航 + Agent状态监控 | 点击章节跳转PRD内容；实时显示各Agent进度 |
| 中间主区域 | PRD内容阅读 | Markdown渲染；选中文字右键提问；图片点击放大查看识别结果 |
| 右侧栏 | 问题列表 + 追问交互 | 问题卡片操作；追问回复；筛选/排序 |

### 2.3 页面状态设计

#### 审查工作台的状态流转

| 页面状态 | 展示内容 | 用户可操作 |
|----------|---------|-----------|
| **审查中** (RUNNING) | PRD内容 + Agent进度动画 + 已出问题的实时更新 | 终止审查、回复追问(自主模式) |
| **审查完成** (COMPLETED) | PRD内容 + 完整问题列表 | 确认/误报/关闭问题、重新审查、导出报告 |
| **审查超时** (TIMEOUT) | PRD内容 + 部分问题列表（标注"超时未完成"） | 同COMPLETED + 可重新审查 |
| **已取消** (CANCELLED) | PRD内容 + 已产生的部分问题 | 可重新审查 |

### 2.4 关键交互细节

#### 审查中状态的实时更新

1. 页面打开后自动建立 WebSocket 连接
2. Agent每产出一个问题，前端实时追加到右侧问题列表
3. 左侧Agent状态实时更新（进度条 + 问题数）
4. 底部状态栏显示"已耗时 Xs | PM ✅4 DEV ⏳ QA ⏳"

#### 追问交互（自主模式）

1. Agent发出追问时，右侧栏"追问面板"出现新追问卡片（带动画高亮）
2. 同时页面顶部弹出Toast："PM Agent 提出了1个追问"
3. 追问卡片包含：Agent名称、追问内容、关联章节链接、[回复] [跳过] 按钮
4. 点击[回复]展开文本输入框，用户填写后点击[提交]
5. 点击[跳过]确认弹窗后，追问标记为"已跳过"
6. 用户未在页面上时，追问通过站内信通知（下次登录可见）

#### 一键复制

1. 问题卡片右上角[复制]按钮
2. 点击后复制格式化文本到剪贴板
3. Toast提示"已复制，可直接粘贴到TAPD工单"

---

## 三、自主Agent追问的实时交互机制

### 3.1 技术方案：WebSocket

**选型理由**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| WebSocket | 实时性好、服务端主动推送、适合双向通信 | 需维护长连接 | ✅ 采用 |
| 前端轮询 | 实现简单 | 延迟高（5-10s）、服务端压力大 | ❌ 不采用 |
| SSE | 单向推送简单 | 仅服务端→客户端单向 | 可备选（降级方案） |

**降级策略**：WebSocket连接失败时，降级为SSE（Server-Sent Events）；SSE也失败时，降级为5秒间隔轮询 `GET /sessions/{id}`。

### 3.2 WebSocket 连接规范

**连接地址**：`ws://{host}/api/v1/ws/sessions/{session_id}`

**认证**：连接时通过 query 参数传递 JWT：`?token=eyJhbGciOi...`

**消息格式**（服务端→客户端）：

```json
{
  "type": "ISSUE_CREATED | AGENT_STATUS_CHANGED | FOLLOW_UP_CREATED | SESSION_COMPLETED | SESSION_TIMEOUT | PROGRESS_UPDATE",
  "payload": { ... },
  "timestamp": "2026-06-11T10:01:30Z"
}
```

**消息类型详细定义**：

| type | payload | 触发时机 |
|------|---------|---------|
| ISSUE_CREATED | ReviewIssue对象 | Agent每发现一个问题时推送 |
| AGENT_STATUS_CHANGED | `{ "agent": "PM_REVIEW", "status": "COMPLETED", "issue_count": 4 }` | Agent状态变更时 |
| FOLLOW_UP_CREATED | FollowUp对象 | 自主模式Agent发出追问时 |
| SESSION_COMPLETED | `{ "session_id": "...", "issue_count": { "HIGH": 2, "MEDIUM": 5, "LOW": 3 } }` | 审查完成时 |
| SESSION_TIMEOUT | `{ "session_id": "...", "partial_issue_count": 6 }` | 审查超时时 |
| PROGRESS_UPDATE | `{ "agent": "DEV_REVIEW", "progress": 0.6 }` | Agent进度更新时（估算） |

**消息格式**（客户端→服务端）：

仅用于追问回复，与 REST API `POST /follow-ups/{id}/answer` 等价，走 WebSocket 减少延迟：

```json
{
  "type": "FOLLOW_UP_ANSWER",
  "payload": {
    "follow_up_id": "FU-001",
    "action": "ANSWER",
    "answer": "支付超时阈值为30秒..."
  }
}
```

### 3.3 前端"等待中"状态展示

| 场景 | 前端展示 |
|------|---------|
| Agent正在审查（无追问） | 左侧Agent状态区：动画旋转图标 + "审查中..."；底部状态栏：已耗时Xs |
| Agent发出追问等待用户回复 | 右侧追问面板高亮新追问卡片 + 顶部Toast + Agent状态区显示"⏸ 等待回复" |
| 用户回复后Agent继续审查 | Agent状态区恢复"审查中..."动画；追问卡片标记为"已回复 ✅" |
| 多个Agent同时追问 | 追问面板按时间排序展示所有待回复追问；每个追问标注来源Agent |
| 追问达到上限 | 追问面板顶部显示"追问次数已达上限(5/5)"；不再出现新追问卡片 |

---

## 四、Agent Prompt 设计（MVP版本）

> 以下为MVP版本的System Prompt草稿。上线前需基于真实PRD样本进行调优（至少10份不同类型的PRD测试），记录调优过程和效果对比。

### 4.1 PM Review Agent — System Prompt

```
你是一位资深产品经理，现在负责从产品视角审查PRD文档。你的目标是发现PRD中的逻辑漏洞、信息缺失和不一致之处，确保需求的完整性和可执行性。

## 你的角色
你是一位有8年经验的高级产品经理，擅长需求拆解、状态机设计和用户体验审查。你以严谨著称，不会放过任何逻辑漏洞。

## 审查维度与检查清单

你必须从以下6个维度逐一审查PRD：

### 1. 用户流程完整性
- 主流程是否有明确的起点和终点？
- 每个决策节点是否覆盖了所有分支（是/否/异常）？
- 是否存在"用户不知道下一步该做什么"的情况？
- 并发操作（如多人同时操作同一资源）是否考虑？

### 2. 状态流转
- 是否定义了完整的状态机（所有状态、转换条件、触发事件）？
- 是否存在不可达状态（无法从任何路径到达）？
- 是否存在无法退出的状态（没有转换条件离开）？
- 状态回退（如审批驳回、取消订单）是否定义？
- 状态流转是否有时序约束（如A必须在B之后）？

### 3. 埋点缺失
- 核心用户行为是否有埋点定义？
- 业务漏斗的关键步骤是否有数据采集方案？
- 异常路径（如支付失败）是否有埋点？
- 是否定义了埋点触发时机和采集字段？

### 4. 文案一致性
- 同一概念在不同章节的用词是否一致？（如"订单"/"工单"/"工单"混用）
- UI文案与功能描述是否匹配？
- 按钮/操作名称是否在全文统一？（如"确认"/"提交"/"保存"混用）

### 5. 边界条件
- 数值边界（最大值/最小值/默认值）是否定义？
- 空值/null/undefined的处理是否说明？
- 列表为空时的展示是否定义？
- 长文本/大数量的展示策略是否说明？

### 6. 异常流
- 操作失败后的处理是否定义？（如网络超时、服务端错误）
- 并发冲突的处理是否定义？（如两人同时编辑）
- 数据不一致的修复方案是否说明？
- 第三方服务不可用时的降级策略是否定义？

## 输出格式

对每个发现的问题，你必须按以下JSON格式输出：

```json
{
  "title": "问题标题（简明一句话，不超过30字）",
  "issue_type": "LOGIC_GAP",
  "severity": "HIGH | MEDIUM | LOW",
  "description": "问题详细描述，必须引用PRD原文片段，用「」标注引用内容",
  "suggestion": "建议的解决方案或补充方案",
  "prd_section": "对应PRD章节路径",
  "prd_quote": "PRD原文中被引用的片段（至少一句话）",
  "confidence": 0.85,
  "image_ref": null
}
```

## 严重等级判定标准
- HIGH：逻辑矛盾/流程断链/可能导致线上事故/用户资金损失
- MEDIUM：信息缺失/边界未定义/可能导致开发返工
- LOW：文案不一致/格式问题/优化建议

## 置信度评分标准
- 0.9-1.0：PRD原文有明确矛盾或缺失，确信是问题
- 0.7-0.9：大概率是问题，但存在理解歧义的可能
- 0.5-0.7：可能是问题，需要人工进一步确认
- <0.5：不确定，不建议标记为问题

## 约束
1. 每个问题的description必须引用PRD原文，不可凭空编造
2. 不输出与PRD内容无关的问题
3. 不对PRD的写作风格或格式做评价（除非影响理解）
4. 最多输出30个问题
5. 如果PRD质量较高、问题较少，不要为了凑数而降低标准
6. 如果某个维度未发现问题，输出"该维度未发现问题"即可
```

### 4.2 Dev Review Agent — System Prompt

```
你是一位资深技术架构师，现在负责从技术实现视角审查PRD文档。你的目标是发现PRD中的技术风险、接口设计缺陷和实现障碍，确保需求在技术层面可行且完整。

## 你的角色
你是一位有10年经验的技术架构师，擅长系统设计、接口规范和性能优化。你对技术风险极为敏感，能在需求阶段就发现潜在的实现障碍。

## 审查维度与检查清单

### 1. 技术风险
- PRD中描述的功能在当前技术栈下是否可实现？
- 是否有未评估的第三方依赖（新SDK/新API/新服务）？
- 是否存在已知的技术限制（如浏览器兼容性、移动端限制）？
- 数据量和性能要求是否在当前架构下可承受？

### 2. 接口依赖
- 接口契约是否定义（URL、Method、入参、出参、错误码）？
- 上下游接口是否对齐（调用方的请求是否匹配提供方的响应）？
- 接口版本兼容策略是否说明？
- 是否有循环依赖（A调B、B调A）？
- 第三方接口的SLA和降级方案是否考虑？

### 3. 数据一致性
- 跨表/跨服务的数据更新是否有事务保障方案？
- 缓存与数据库的一致性策略是否定义（更新时机、失效策略）？
- 分布式场景下是否有最终一致性保障？
- 数据迁移方案是否说明（涉及表结构变更时）？

### 4. 幂等问题
- 重复提交场景（用户双击、网络重试、消息重放）是否有幂等设计？
- 支付/库存/积分等关键操作是否防重？
- 幂等的粒度是否合理（全局幂等 vs 业务幂等）？
- 幂等Token的生命周期管理是否说明？

### 5. 并发问题
- 高并发场景是否有限流/队列/削峰方案？
- 竞态条件是否考虑（如秒杀、库存扣减）？
- 数据库锁策略是否说明（乐观锁 vs 悲观锁）？
- 是否有热点数据/热点Key的应对方案？

### 6. 兼容性
- 是否涉及老版本兼容（数据迁移、接口兼容、功能开关）？
- 数据迁移方案是否说明（全量/增量、回滚方案）？
- 灰度发布策略是否考虑？
- 是否有AB测试的需求？

## 输出格式

同PM Review Agent的JSON格式，但issue_type使用以下值：
- TECHNICAL_RISK：技术风险
- DATA_INCONSISTENCY：数据一致性问题
- LOGIC_GAP：逻辑遗漏（技术视角）

## 严重等级判定标准
- HIGH：技术不可行/可能导致线上事故（数据丢失/资金损失/服务不可用）
- MEDIUM：技术方案不完整/可能导致返工/性能隐患
- LOW：技术建议优化/非关键兼容性问题

## 置信度评分标准
同PM Review Agent。

## 约束
1. 每个问题的description必须引用PRD原文，不可凭空编造
2. 不假设具体的技术实现方案（除非PRD中已提及），只指出风险
3. 给出的suggestion应是方向性建议，不是详细设计文档
4. 最多输出30个问题
5. 如果某个技术栈未在PRD中说明，基于常见技术栈进行审查，并在问题中标注"基于假设技术栈"
```

### 4.3 QA Review Agent — System Prompt

```
你是一位资深测试工程师，现在负责从测试视角审查PRD文档。你的目标是发现PRD中测试覆盖不足的地方，生成边界测试Case和异常流Case，确保需求在测试层面可验证。

## 你的角色
你是一位有7年经验的测试专家，擅长边界值分析、状态机测试和异常场景构造。你总能想到别人想不到的边界条件。

## 审查维度与检查清单

### 1. 边界条件
- 数值边界：最大值/最小值/零值/负值是否可推导测试Case？
- 字符串边界：空串/超长串/特殊字符/编码问题是否覆盖？
- 时间边界：跨天/跨月/闰年/时区是否考虑？
- 数组边界：空列表/单元素列表/超大列表是否定义？
- 输入格式边界：格式校验规则是否明确到可编写测试？

### 2. 异常流程
- 操作失败路径（服务端错误、网络超时、权限不足）是否有测试覆盖？
- 异常数据输入（脏数据、注入、越权访问）是否考虑？
- 第三方依赖失败时的降级路径是否可测试？
- 数据部分失败（批量操作中部分成功部分失败）的处理是否定义？

### 3. Case遗漏
- 状态流转全路径是否可生成完整测试Case？
- 权限边界（未登录/无权限/越权）是否覆盖？
- 并发操作（同时提交、同时修改）是否可构造测试场景？
- 回退操作（撤销、退回、回滚）是否可测试？

### 4. 状态覆盖
- 所有状态转换是否有对应测试场景？
- 状态回退（如审批驳回到起草）是否考虑？
- 非法状态转换（如从"已完成"直接到"已取消"）是否防护？
- 状态超时（如"待支付"超过24小时）的处理是否可测试？

## 输出格式

同PM Review Agent的JSON格式，但issue_type使用 TEST_MISSING。

此外，对于每个问题，suggestion字段应包含一个建议的测试Case：

```json
{
  "suggestion": "建议补充以下测试Case：\n1. [前置条件] 用户已登录，购物车有1件商品\n   [操作] 提交订单时支付超时\n   [预期] 订单状态变为'待支付'，库存不扣减，提示'支付超时，请重新支付'"
}
```

## 严重等级判定标准
- HIGH：核心功能不可测试/存在必现的缺陷路径/安全漏洞
- MEDIUM：异常路径未覆盖/边界条件未定义/测试Case不完整
- LOW：非核心场景未覆盖/优化建议

## 约束
1. 每个问题的suggestion必须包含至少一个具体的测试Case（含前置条件、操作步骤、预期结果）
2. 优先关注核心功能路径和异常路径，不纠结于UI细节
3. 不输出与PRD无关的通用测试建议（如"测试浏览器兼容性"除非PRD涉及）
4. 最多输出30个问题
5. 如果PRD已经非常详细，可测试性好，只需指出少量遗漏即可
```

### 4.4 自主模式追加Prompt

当用户选择自主Agent模式时，在上述System Prompt末尾追加以下指令：

```
## 自主审查模式

你当前运行在"自主审查模式"中。除了标准审查外，你还可以：

### 追问
如果你在审查过程中发现PRD存在信息缺失或歧义，导致你无法判断是否存在问题，你可以向用户发起追问。

追问格式：
```json
{
  "type": "FOLLOW_UP",
  "question": "你的追问内容，需明确具体、便于用户回答",
  "prd_section": "关联的PRD章节",
  "reason": "为什么需要这个信息（解释你的判断依据）"
}
```

追问规则：
1. 只在信息缺失导致无法判断问题是否存在时才追问，不为细节纠缠
2. 追问必须具体，不要问开放性问题（❌"请补充更多信息"，✅"第3章支付流程中未定义超时阈值，请问超时时间是多少秒？"）
3. 单次审查最多发起5次追问
4. 追问后等待用户回复再继续审查

### 追加审查
如果用户回复追问后提供了新信息，你需要基于新信息进行追加审查（第二轮），检查新信息是否引入了新问题。

### 联网搜索（如已启用）
如果PRD中提到你不熟悉的技术或行业标准，你可以搜索相关信息辅助判断。搜索结果必须标注来源URL。
```

---

## 五、数据库 DDL / Schema

### 5.1 PostgreSQL DDL

```sql
-- ============================================
-- AI需求评审Agent 数据库 Schema
-- PostgreSQL 15+
-- ============================================

-- 用户表
CREATE TABLE users (
    user_id         VARCHAR(32) PRIMARY KEY,
    username        VARCHAR(64) NOT NULL UNIQUE,
    password_hash   VARCHAR(256) NOT NULL,
    display_name    VARCHAR(64) NOT NULL,
    email           VARCHAR(128),
    role            VARCHAR(16) NOT NULL DEFAULT 'PM',  -- PM / DEV / QA / SM / ADMIN
    status          VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE / DISABLED
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role ON users(role);

-- 项目表
CREATE TABLE projects (
    project_id          VARCHAR(32) PRIMARY KEY,
    name                VARCHAR(128) NOT NULL,
    tapd_project_id     VARCHAR(32),
    tapd_token_encrypted TEXT,  -- AES-256加密存储
    config              JSONB NOT NULL DEFAULT '{
        "text_model": "deepseek-v3",
        "multimodal_model": "qwen-vl-max",
        "auto_switch_model": true,
        "confidence_threshold_low": 0.5,
        "confidence_threshold_high": 0.8,
        "max_review_rounds_deterministic": 1,
        "max_review_rounds_autonomous": 3,
        "max_follow_up_questions": 5,
        "max_issues_per_agent": 30,
        "session_timeout_deterministic_min": 5,
        "session_timeout_autonomous_min": 10
    }'::jsonb,
    status              VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE / ARCHIVED
    created_by          VARCHAR(32) REFERENCES users(user_id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_projects_tapd ON projects(tapd_project_id);

-- 项目成员表（多对多）
CREATE TABLE project_members (
    id          SERIAL PRIMARY KEY,
    project_id  VARCHAR(32) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    user_id     VARCHAR(32) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role        VARCHAR(16) NOT NULL DEFAULT 'PM',  -- PM / DEV / QA / SM / ADMIN
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(project_id, user_id)
);

CREATE INDEX idx_pm_project ON project_members(project_id);
CREATE INDEX idx_pm_user ON project_members(user_id);

-- 审查会话表
CREATE TABLE review_sessions (
    session_id      VARCHAR(32) PRIMARY KEY,
    project_id      VARCHAR(32) NOT NULL REFERENCES projects(project_id),
    prd_content     TEXT NOT NULL,
    prd_source      VARCHAR(16) NOT NULL,  -- TEXT / FILE / TAPD
    prd_structure   JSONB,  -- 解析后的PRD章节结构
    prd_images      JSONB,  -- 图片列表及识别结果
    tapd_story_id   VARCHAR(32),
    agent_mode      VARCHAR(16) NOT NULL DEFAULT 'DETERMINISTIC',  -- DETERMINISTIC / AUTONOMOUS
    status          VARCHAR(16) NOT NULL DEFAULT 'RUNNING',  -- RUNNING / COMPLETED / TIMEOUT / CANCELLED
    initiator_id    VARCHAR(32) NOT NULL REFERENCES users(user_id),
    agent_results   JSONB,  -- 各Agent审查结果汇总
    follow_up_questions JSONB,  -- 自主模式追问记录
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_project ON review_sessions(project_id);
CREATE INDEX idx_sessions_status ON review_sessions(status);
CREATE INDEX idx_sessions_initiator ON review_sessions(initiator_id);
CREATE INDEX idx_sessions_created ON review_sessions(created_at DESC);

-- prd_structure JSON结构说明：
-- {
--   "sections": [
--     {
--       "section_id": "S1",
--       "title": "一、项目背景",
--       "level": 1,
--       "char_range": [0, 500],
--       "children": [...]
--     }
--   ],
--   "total_sections": 15,
--   "total_chars": 8500
-- }

-- prd_images JSON结构说明：
-- [
--   {
--     "image_id": "IMG-001",
--     "filename": "flow.png",
--     "source": "UPLOAD | TAPD_ATTACHMENT",
--     "content_type": "image/png",
--     "filesize": 256000,
--     "recognition_status": "PENDING | PROCESSING | COMPLETED | FAILED",
--     "recognition_result": "识别出的文本和结构描述...",
--     "section_id": "S3.2"
--   }
-- ]

-- agent_results JSON结构说明：
-- {
--   "PM_REVIEW": {
--     "status": "COMPLETED",
--     "round": 1,
--     "issue_count": 4,
--     "started_at": "...",
--     "completed_at": "...",
--     "model_used": "deepseek-v3",
--     "tokens_used": { "input": 8000, "output": 3000 }
--   },
--   "DEV_REVIEW": { ... },
--   "QA_REVIEW": { ... }
-- }

-- follow_up_questions JSON结构说明：
-- [
--   {
--     "follow_up_id": "FU-001",
--     "source_agent": "PM_REVIEW",
--     "question": "...",
--     "prd_section": "...",
--     "reason": "...",
--     "status": "PENDING | ANSWERED | SKIPPED",
--     "answer": "...",
--     "round": 1,
--     "created_at": "...",
--     "answered_at": "..."
--   }
-- ]

-- 审查问题表
CREATE TABLE review_issues (
    issue_id        VARCHAR(32) PRIMARY KEY,
    session_id      VARCHAR(32) NOT NULL REFERENCES review_sessions(session_id) ON DELETE CASCADE,
    source_agent    VARCHAR(16) NOT NULL,  -- PM_REVIEW / DEV_REVIEW / QA_REVIEW
    issue_type      VARCHAR(32) NOT NULL,  -- TECHNICAL_RISK / LOGIC_GAP / TEST_MISSING / DATA_INCONSISTENCY
    severity        VARCHAR(8) NOT NULL,   -- HIGH / MEDIUM / LOW
    title           VARCHAR(200) NOT NULL,
    description     TEXT NOT NULL,
    suggestion      TEXT,
    prd_section     VARCHAR(200),
    prd_quote       TEXT,  -- PRD原文引用片段
    image_ref       VARCHAR(200),  -- 引用的图片来源
    confidence      DECIMAL(3,2) NOT NULL DEFAULT 0.80,
    confidence_label VARCHAR(8) NOT NULL DEFAULT 'HIGH',  -- HIGH / MEDIUM / LOW
    status          VARCHAR(20) NOT NULL DEFAULT 'OPEN',  -- OPEN / CONFIRMED / FALSE_POSITIVE / RESOLVED / DEFERRED
    review_round    INT NOT NULL DEFAULT 1,
    resolved_by     VARCHAR(32) REFERENCES users(user_id),
    resolution_note TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_issues_session ON review_issues(session_id);
CREATE INDEX idx_issues_agent ON review_issues(source_agent);
CREATE INDEX idx_issues_severity ON review_issues(severity);
CREATE INDEX idx_issues_status ON review_issues(status);
CREATE INDEX idx_issues_type ON review_issues(issue_type);
CREATE INDEX idx_issues_confidence ON review_issues(confidence);
CREATE INDEX idx_issues_session_severity ON review_issues(session_id, severity);

-- 问题评论表
CREATE TABLE issue_comments (
    comment_id      VARCHAR(32) PRIMARY KEY,
    issue_id        VARCHAR(32) NOT NULL REFERENCES review_issues(issue_id) ON DELETE CASCADE,
    user_id         VARCHAR(32) NOT NULL REFERENCES users(user_id),
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_comments_issue ON issue_comments(issue_id);
CREATE INDEX idx_comments_user ON issue_comments(user_id);

-- 操作审计日志表
CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(32) REFERENCES users(user_id),
    project_id      VARCHAR(32),
    session_id      VARCHAR(32),
    action          VARCHAR(64) NOT NULL,  -- SESSION_CREATED / ISSUE_CONFIRMED / ISSUE_FALSE_POSITIVE / ...
    detail          JSONB,  -- 操作详情
    ip_address      VARCHAR(45),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_project ON audit_logs(project_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);

-- 站内通知表
CREATE TABLE notifications (
    notification_id  VARCHAR(32) PRIMARY KEY,
    user_id          VARCHAR(32) NOT NULL REFERENCES users(user_id),
    type             VARCHAR(32) NOT NULL,  -- SESSION_COMPLETED / FOLLOW_UP / SESSION_TIMEOUT / TOKEN_EXPIRED
    title            VARCHAR(200) NOT NULL,
    content          TEXT NOT NULL,
    related_session_id VARCHAR(32),
    is_read          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_user ON notifications(user_id, is_read, created_at DESC);
CREATE INDEX idx_notifications_type ON notifications(type);

-- 严重等级变更记录表
CREATE TABLE severity_change_logs (
    id              BIGSERIAL PRIMARY KEY,
    issue_id        VARCHAR(32) NOT NULL REFERENCES review_issues(issue_id),
    old_severity    VARCHAR(8) NOT NULL,
    new_severity    VARCHAR(8) NOT NULL,
    reason          TEXT NOT NULL,
    changed_by      VARCHAR(32) NOT NULL REFERENCES users(user_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_severity_change_issue ON severity_change_logs(issue_id);
```

### 5.2 JSON字段结构速查

| 字段 | 所在表 | 结构说明 |
|------|--------|---------|
| config | projects | 见DDL内注释 |
| prd_structure | review_sessions | 见DDL内注释 |
| prd_images | review_sessions | 见DDL内注释 |
| agent_results | review_sessions | 见DDL内注释 |
| follow_up_questions | review_sessions | 见DDL内注释 |
| detail | audit_logs | `{ "field": "status", "old_value": "OPEN", "new_value": "CONFIRMED" }` |

---

## 六、前端 UI 组件库选型

### 6.1 推荐方案：Ant Design + Tailwind CSS

| 维度 | 方案A：Ant Design | 方案B：shadcn/ui | 方案C：纯Tailwind CSS |
|------|-------------------|-----------------|---------------------|
| 组件丰富度 | ⭐⭐⭐⭐⭐（60+组件） | ⭐⭐⭐⭐（复制式，灵活但需组装） | ⭐⭐（需从零构建） |
| 企业级表单/表格 | ⭐⭐⭐⭐⭐（ProTable/ProForm） | ⭐⭐⭐（需自建） | ⭐（需自建） |
| 中文支持 | ⭐⭐⭐⭐⭐（原生中文） | ⭐⭐⭐（需配置） | ⭐⭐（需配置） |
| 定制灵活性 | ⭐⭐⭐（Design Token可定制） | ⭐⭐⭐⭐⭐（源码级控制） | ⭐⭐⭐⭐⭐ |
| 开发速度 | ⭐⭐⭐⭐⭐（开箱即用） | ⭐⭐⭐⭐（复制后可用） | ⭐⭐（需大量工作） |
| Markdown渲染 | 需搭配react-markdown | 需搭配react-markdown | 需搭配react-markdown |
| 与Next.js兼容 | ⭐⭐⭐⭐（App Router需额外配置） | ⭐⭐⭐⭐⭐（原生支持） | ⭐⭐⭐⭐⭐ |

**推荐方案**：**Ant Design 5.x + Tailwind CSS**

**理由**：

1. **表单/表格是企业级核心**：审查问题列表（筛选/排序/分页）、追问面板、风险仪表盘都需要复杂表格和表单交互，Ant Design 的 ProTable/ProForm 可大幅提效
2. **中文友好**：日期选择器、空状态、分页等组件原生中文，无需额外配置
3. **Tailwind补充布局**：Ant Design 的布局系统较弱，Tailwind 用于页面级布局（三栏、flex、grid）
4. **MVP速度优先**：Ant Design 开箱即用，2周内可搭建完整UI框架

### 6.2 关键第三方依赖

| 用途 | 依赖 | 说明 |
|------|------|------|
| UI组件库 | antd@5.x | 核心UI组件 |
| CSS工具 | tailwindcss@3.x | 布局和自定义样式 |
| Markdown渲染 | react-markdown + remark-gfm | PRD内容区Markdown渲染 |
| 代码高亮 | rehype-highlight | PRD中代码块高亮 |
| 图表 | @ant-design/charts 或 recharts | 风险仪表盘图表 |
| WebSocket | 原生WebSocket API + reconnecting-websocket | 实时通信 |
| 文件上传 | antd Upload组件 + tus-js-client | 大文件分片上传 |
| PDF导出 | @react-pdf/renderer | 审查报告PDF导出 |
| Excel导出 | xlsx | 问题清单Excel导出 |
| 复制到剪贴板 | navigator.clipboard API | 一键复制问题内容 |

### 6.3 不推荐的方案及原因

| 方案 | 不推荐原因 |
|------|-----------|
| Material UI | 中文支持差，表格/表单能力不如Ant Design |
| Chakra UI | 企业级复杂组件不足，社区生态不如Ant Design |
| 纯Tailwind CSS | MVP阶段需要从零构建所有组件，开发速度慢 |
| Streamlit | 不适合企业级复杂交互页面，且为Python后端渲染 |

---

## 七、Agent 输出 JSON 解析策略

### 7.1 问题分析

Prompt 要求三个 Agent 按 JSON 格式输出审查问题，但 LLM 实际响应可能存在：

| 异常场景 | 示例 |
|----------|------|
| Markdown 代码块包裹 | ```` ```json\n{...}\n``` ```` |
| 前后附加大段解释文字 | `以下是审查发现的问题：\n```json\n{...}\n```\n以上是全部问题` |
| JSON 外层包了数组但 Prompt 要求单条 | `[{...}, {...}]` 而非逐条 |
| JSON 中嵌套了未转义的换行/引号 | `"description": "第一行\n第二行"` |
| JSON 截断（Token 超限） | `{"title": "支付流程...", "issue_type": "LOGIC_G` |
| 多个 JSON 对象连续输出 | `{...}\n{...}\n{...}` |

### 7.2 解析策略（三层防御）

```
LLM 原始响应
    │
    ▼
┌─────────────────────────────────────────────┐
│ 第一层：结构化输出约束（预防层）                  │
│   response_format: json_object               │
│   + Pydantic Model 校验                       │
│   → 合规率预期 85-90%                          │
└──────────────────────┬──────────────────────┘
                       │ 失败
                       ▼
┌─────────────────────────────────────────────┐
│ 第二层：正则提取 + 修复（修复层）                 │
│   1. 提取 Markdown 代码块中的 JSON              │
│   2. 提取首个 { ... } 或 [ ... ] 块             │
│   3. 修复常见格式错误（尾逗号、未转义字符）         │
│   4. 如果是数组，逐条解析                        │
│   → 合规率预期 95-98%                          │
└──────────────────────┬──────────────────────┘
                       │ 失败
                       ▼
┌─────────────────────────────────────────────┐
│ 第三层：重试 + 降级（兜底层）                     │
│   1. 重试：相同 Prompt + "请仅输出JSON" 追加     │
│      最多重试 2 次                              │
│   2. 降级：将原始响应当作纯文本处理               │
│      - 标记 issue_type = "UNSTRUCTURED"       │
│      - 将全文作为 description                   │
│      - confidence = 0.3（强制低置信度）          │
│      - 需人工审核                               │
│   → 兜底率 100%                                │
└─────────────────────────────────────────────┘
```

### 7.3 第一层：结构化输出约束（首选方案）

**方案选择**：使用 `response_format: json_object`（OpenAI 兼容接口原生支持）+ Pydantic Model 校验

**不选择 StructuredOutputParser 的理由**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| `response_format: json_object` | 模型层面强制 JSON 输出；兼容 OpenAI / DeepSeek / Qwen | 不保证 JSON 内部结构严格匹配 Schema | ✅ 采用，配合 Pydantic 补位 |
| StructuredOutputParser | 依赖 LangChain 封装 | 换模型时行为不一致；对中文 Prompt 支持不稳定；增加 LangChain 强耦合 | ❌ 不采用 |
| Function Calling / Tool Calling | 结构最严格 | 不是所有模型都支持；Qwen 部分版本不支持；语义偏离审查场景 | ❌ 不采用 |

**Pydantic 校验模型**：

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class IssueType(str, Enum):
    TECHNICAL_RISK = "TECHNICAL_RISK"
    LOGIC_GAP = "LOGIC_GAP"
    TEST_MISSING = "TEST_MISSING"
    DATA_INCONSISTENCY = "DATA_INCONSISTENCY"
    UNSTRUCTURED = "UNSTRUCTURED"

class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class ReviewIssueModel(BaseModel):
    title: str = Field(max_length=200, description="问题标题，简明一句话")
    issue_type: IssueType
    severity: Severity
    description: str = Field(description="问题详细描述，需引用PRD原文")
    suggestion: Optional[str] = Field(default=None, description="建议方案")
    prd_section: Optional[str] = Field(default=None, description="PRD章节路径")
    prd_quote: Optional[str] = Field(default=None, description="PRD原文引用片段")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度评分")
    image_ref: Optional[str] = Field(default=None, description="引用的图片来源")

class ReviewOutputModel(BaseModel):
    issues: List[ReviewIssueModel] = Field(description="审查发现的问题列表")
```

**校验流程**：

```python
def parse_agent_response(raw: str, agent_name: str) -> List[ReviewIssueModel]:
    """
    解析 Agent 响应，三层防御策略
    """
    # ---- 第一层：直接 JSON 解析 + Pydantic 校验 ----
    try:
        parsed = json.loads(raw)
        output = ReviewOutputModel(**parsed) if "issues" in parsed else ReviewOutputModel(issues=[ReviewIssueModel(**parsed)])
        return output.issues
    except (json.JSONDecodeError, ValidationError):
        pass  # 进入第二层

    # ---- 第二层：正则提取 + 修复 ----
    extracted = extract_json_from_markdown(raw)  # 提取代码块
    if extracted is None:
        extracted = extract_first_json_block(raw)  # 提取首个 {}/[] 块
    if extracted:
        try:
            fixed = repair_common_json_errors(extracted)  # 修复尾逗号等
            parsed = json.loads(fixed)
            # 如果是数组，包装为 ReviewOutputModel
            if isinstance(parsed, list):
                output = ReviewOutputModel(issues=[ReviewIssueModel(**item) for item in parsed])
            else:
                output = ReviewOutputModel(issues=[ReviewIssueModel(**parsed)])
            return output.issues
        except (json.JSONDecodeError, ValidationError):
            pass  # 进入第三层

    # ---- 第三层：重试 + 降级 ----
    return retry_or_fallback(raw, agent_name)
```

### 7.4 第二层：正则提取与修复逻辑

```python
import re

def extract_json_from_markdown(text: str) -> Optional[str]:
    """提取 Markdown 代码块中的 JSON"""
    pattern = r'```(?:json)?\s*\n([\s\S]*?)\n```'
    matches = re.findall(pattern, text)
    if matches:
        # 优先取最长的匹配（最有可能是完整数据）
        return max(matches, key=len).strip()
    return None

def extract_first_json_block(text: str) -> Optional[str]:
    """提取文本中首个完整的 JSON 对象或数组"""
    # 尝试匹配数组 [...]
    bracket_match = re.search(r'\[[\s\S]*\]', text)
    brace_match = re.search(r'\{[\s\S]*\}', text)
    # 选择出现位置更靠前的
    candidates = []
    if bracket_match:
        candidates.append(bracket_match.group(0))
    if brace_match:
        candidates.append(brace_match.group(0))
    if not candidates:
        return None
    return min(candidates, key=lambda c: text.index(c))

def repair_common_json_errors(text: str) -> str:
    """修复常见的 JSON 格式错误"""
    # 移除尾逗号：}, ] 前的逗号
    text = re.sub(r',\s*([}\]])', r'\1', text)
    # 修复未转义的换行符在字符串值中
    text = re.sub(r'(?<=": ")(.*?)(?=")', lambda m: m.group(1).replace('\n', '\\n'), text)
    return text
```

### 7.5 第三层：重试与降级

```python
MAX_PARSE_RETRIES = 2

def retry_or_fallback(raw: str, agent_name: str) -> List[ReviewIssueModel]:
    """重试 + 降级策略"""
    # 重试：追加提示语
    for attempt in range(MAX_PARSE_RETRIES):
        retry_prompt = f"""上一次你的输出格式不正确，无法解析为JSON。请严格按照以下格式输出，不要包含任何其他文字：

```json
{{"issues": [{{"title": "...", "issue_type": "...", "severity": "...", "description": "...", "suggestion": "...", "prd_section": "...", "prd_quote": "...", "confidence": 0.0, "image_ref": null}}]}}
```"""
        new_response = call_llm_with_retry(raw, retry_prompt)  # 带原始上下文重试
        try:
            parsed = json.loads(extract_json_from_markdown(new_response) or new_response)
            output = ReviewOutputModel(**parsed) if "issues" in parsed else ReviewOutputModel(issues=[ReviewIssueModel(**parsed)])
            return output.issues
        except (json.JSONDecodeError, ValidationError):
            continue

    # 降级：将原始文本作为非结构化问题
    return [ReviewIssueModel(
        title=f"[{agent_name}] 非结构化审查输出",
        issue_type=IssueType.UNSTRUCTURED,
        severity=Severity.LOW,
        description=raw[:2000],  # 截断防溢出
        suggestion="AI输出格式异常，请人工审核原始内容",
        prd_section=None,
        prd_quote=None,
        confidence=0.3,
        image_ref=None
    )]
```

### 7.6 解析策略与 LangGraph 的集成

在 LangGraph 的每个 Agent 节点中，解析逻辑的位置：

```
Agent 节点执行流程：
1. 构建 Prompt → 调用 LLM（response_format: json_object）
2. 获取 LLM 原始响应
3. 调用 parse_agent_response(raw, agent_name)
4. 解析成功 → 写入 State.issues
5. 解析降级 → 写入 State.issues（标记 UNSTRUCTURED）+ 记录日志
6. 进入下一个节点
```

**关键约束**：

| 项目 | 值 | 说明 |
|------|-----|------|
| 单次 LLM 调用超时 | 60s | 含重试在内 |
| 重试次数上限 | 2 | 每个Agent节点 |
| 降级问题 confidence | 0.3 | 强制低置信度 |
| 降级问题 severity | LOW | 强制低等级 |
| 解析失败日志级别 | WARNING | 不阻断审查流程 |
| 非结构化问题需人工审核 | 是 | 前端标记"需人工审核"标签 |

---

## 八、文件上传存储方案

### 8.1 需求分析

| 文件类型 | 来源 | 大小范围 | 用途 | 生命周期 |
|----------|------|---------|------|---------|
| PDF | 用户上传 | 100KB-20MB | PRD文档，解析后提取文本和图片 | 审查完成后可清理 |
| Word (.docx) | 用户上传 | 50KB-10MB | PRD文档，解析后提取文本和图片 | 审查完成后可清理 |
| 图片 (.png/.jpg/.svg) | 用户上传 / TAPD附件 | 10KB-5MB | PRD中的流程图/架构图/原型图 | 识别完成后可清理 |
| TAPD附件 | TAPD API下载 | 不定 | 关联需求的附件 | 下载后本地缓存 |

**核心决策**：PRD V1.1 明确"不保留原图，仅保留识别结果文本"。因此文件存储是**临时性**的，审查完成后应清理原始文件。

### 8.2 存储方案选型

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 本地文件系统 | 零依赖、MVP最快 | 不支持多实例部署、无容灾 | ✅ MVP 采用 |
| MinIO (S3兼容) | 支持多实例、可迁移K8s | 需额外部署服务 | Phase 2 切换 |
| 云S3 (腾讯云COS) | 完全托管 | 依赖云服务、MVP成本高 | 视部署环境决定 |

**MVP 决策**：本地文件系统 + MinIO 作为 Phase 2 升级路径。

### 8.3 本地文件系统方案详细设计

#### 目录结构

```
/data/uploads/
├── {project_id}/
│   └── {session_id}/
│       ├── prd_source/           # PRD原始文件
│       │   ├── {file_id}.pdf
│       │   ├── {file_id}.docx
│       │   └── ...
│       ├── images/               # 提取/下载的图片
│       │   ├── {image_id}.png
│       │   └── {image_id}.jpg
│       └── tapd_attachments/     # TAPD下载的附件缓存
│           ├── {attachment_id}.png
│           └── ...
```

#### 文件大小限制

| 参数 | 值 | 说明 |
|------|-----|------|
| 单文件最大 | 20MB | PDF/Word文档 |
| 单图片最大 | 5MB | 流程图/截图 |
| 单次上传总大小 | 50MB | 多文件上传合计 |
| 单会话总文件大小 | 100MB | 含所有PRD文件+图片 |

#### 文件命名规则

```
{file_id} = {timestamp}_{random_8chars}
# 例：20260611103000_a3f8b2c1.pdf
```

#### 上传接口处理流程

```
POST /sessions (multipart/form-data)
    │
    ├─ prd_source = TEXT → 直接存入 review_sessions.prd_content
    │
    ├─ prd_source = FILE →
    │   ├─ 校验文件类型（.pdf/.docx/.png/.jpg/.jpeg/.svg）
    │   ├─ 校验文件大小
    │   ├─ 存储到 /data/uploads/{project_id}/{session_id}/prd_source/
    │   ├─ 解析文本（PDF: PyMuPDF, Word: python-docx）
    │   ├─ 提取图片（PDF内嵌图片 / Word内嵌图片）
    │   ├─ 图片存入 images/ 目录
    │   ├─ 解析结果存入 review_sessions.prd_content（纯文本）
    │   └─ 结构信息存入 review_sessions.prd_structure
    │
    └─ prd_source = TAPD →
        ├─ 调用 TAPD API 获取 Story 详情
        ├─ 提取描述文本
        ├─ 拉取附件到 tapd_attachments/
        ├─ 筛选图片附件存入 images/
        └─ 文本存入 review_sessions.prd_content
```

### 8.4 文件生命周期管理

```
上传 → 解析 → Agent审查 → 审查完成 → 保留期(7天) → 清理
 │       │        │           │           │            │
 │       │        │           │           │            └─ 删除原始文件+图片
 │       │        │           │           └─ 仍可下载原始文件
 │       │        │           └─ 文件仍在，可查看
 │       │        └─ 图片识别结果已存入 prd_images 字段
 │       └─ 文本已存入 prd_content 字段
 └─ 文件落盘
```

**清理策略**：

| 项目 | 策略 |
|------|------|
| 触发时机 | 每日凌晨 02:00 定时任务 |
| 清理条件 | 审查状态为 COMPLETED/TIMEOUT/CANCELLED 且 completed_at 超过 7 天 |
| 清理范围 | prd_source/ + images/ + tapd_attachments/ |
| 数据库保留 | prd_content（纯文本）、prd_structure、prd_images（识别结果）永久保留 |
| 清理日志 | 记录清理的 session_id、文件数、释放空间到 audit_logs |

**为什么保留 7 天**：给用户审查完成后回看原始文件的缓冲期。7 天后仅保留数据库中的文本和图片识别结果。

### 8.5 文件解析技术栈

| 文件类型 | 解析库 | 提取内容 | 图片提取 |
|----------|--------|---------|---------|
| PDF | PyMuPDF (fitz) | 全文文本 + 目录结构 | 支持提取内嵌图片 |
| Word (.docx) | python-docx | 全文文本 + 标题层级 | 支持提取内嵌图片 |
| 图片 (.png/.jpg) | 多模态模型直接识别 | 识别文本和结构 | — |
| SVG | svglib + 多模态模型 | 识别文本和结构 | — |

**PDF 解析注意事项**：

```python
import fitz  # PyMuPDF

def parse_pdf(file_path: str) -> dict:
    doc = fitz.open(file_path)
    text_content = ""
    images = []
    for page_num, page in enumerate(doc):
        text_content += page.get_text()
        # 提取图片
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            # 保存图片到 images/ 目录
            images.append({
                "image_id": f"IMG-{page_num+1}-{img_index+1}",
                "source": "PDF_EMBEDDED",
                "content_type": f"image/{image_ext}",
                "page": page_num + 1
            })
    return {
        "text": text_content,
        "images": images,
        "page_count": len(doc)
    }
```

### 8.6 Phase 2 升级路径：MinIO

MVP 使用本地文件系统，代码层面抽象 `FileStorage` 接口，Phase 2 切换 MinIO 时仅需实现新 Adapter：

```python
from abc import ABC, abstractmethod

class FileStorage(ABC):
    @abstractmethod
    def save(self, project_id: str, session_id: str, category: str, file_id: str, data: bytes) -> str: ...

    @abstractmethod
    def get(self, project_id: str, session_id: str, category: str, file_id: str) -> bytes: ...

    @abstractmethod
    def delete_session_files(self, project_id: str, session_id: str) -> int: ...

class LocalFileStorage(FileStorage):
    """MVP 实现"""
    def __init__(self, base_dir: str = "/data/uploads"):
        self.base_dir = base_dir
    # ... 实现省略

class MinIOFileStorage(FileStorage):
    """Phase 2 实现"""
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str):
        # ...
    # ... 实现省略
```

---

## 九、LangGraph Agent 图结构

### 9.1 State 定义

```python
from typing import TypedDict, List, Optional, Annotated
from langgraph.graph.message import add_messages

class ReviewState(TypedDict):
    """LangGraph 全局 State"""
    # ---- 输入 ----
    session_id: str
    project_id: str
    prd_content: str                    # PRD纯文本内容
    prd_structure: dict                 # PRD章节结构
    prd_images: list[dict]              # 图片列表（含识别结果）
    agent_mode: str                     # DETERMINISTIC / AUTONOMOUS
    project_config: dict                # 项目配置（模型、阈值等）

    # ---- 中间状态 ----
    issues: Annotated[list[dict], add_issues]  # 累积的问题列表
    follow_ups: list[dict]              # 追问列表
    agent_statuses: dict                # 各Agent状态
    current_round: int                  # 当前审查轮次

    # ---- 追问相关（自主模式）----
    pending_follow_ups: list[dict]      # 待回复的追问
    user_answers: list[dict]            # 用户回答

    # ---- 输出 ----
    final_issues: list[dict]            # 最终问题列表
    session_status: str                 # 会话状态

def add_issues(existing: list, new: list) -> list:
    """问题列表合并函数（用于 Annotated 累加）"""
    return existing + new
```

### 9.2 确定性工作流图结构

```
                    ┌──────────────┐
                    │  START       │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  parse_prd   │  解析PRD：提取结构、图片识别
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐ ┌──▼────────┐ ┌─▼─────────┐
       │ pm_review   │ │ dev_review│ │ qa_review  │  ← 三Agent并行
       └──────┬──────┘ └──┬────────┘ └─┬─────────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────▼───────┐
                    │  merge_issues│  合并去重、排序
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │    END       │
                    └──────────────┘
```

**LangGraph 代码骨架**：

```python
from langgraph.graph import StateGraph, END

def build_deterministic_graph() -> StateGraph:
    graph = StateGraph(ReviewState)

    # 添加节点
    graph.add_node("parse_prd", parse_prd_node)
    graph.add_node("pm_review", pm_review_node)
    graph.add_node("dev_review", dev_review_node)
    graph.add_node("qa_review", qa_review_node)
    graph.add_node("merge_issues", merge_issues_node)

    # 设置入口
    graph.set_entry_point("parse_prd")

    # 边：parse_prd → 三Agent并行
    graph.add_edge("parse_prd", "pm_review")
    graph.add_edge("parse_prd", "dev_review")
    graph.add_edge("parse_prd", "qa_review")

    # 边：三Agent → merge
    graph.add_edge("pm_review", "merge_issues")
    graph.add_edge("dev_review", "merge_issues")
    graph.add_edge("qa_review", "merge_issues")

    # 边：merge → END
    graph.add_edge("merge_issues", END)

    return graph.compile()
```

> **三 Agent 并行实现**：LangGraph 通过多个 `add_edge` 从同一源节点指向多个目标节点，天然支持并行执行（无需手动 asyncio.gather）。内部使用 `Send` API 实现 fan-out，三 Agent 各自独立运行，全部完成后汇聚到 `merge_issues` 节点。

### 9.3 自主模式图结构

```
                    ┌──────────────┐
                    │  START       │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  parse_prd   │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐ ┌──▼────────┐ ┌─▼─────────┐
       │ pm_review   │ │ dev_review│ │ qa_review  │  ← 三Agent并行
       └──────┬──────┘ └──┬────────┘ └─┬─────────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────▼───────┐
                    │ check_follow │  检查是否有追问
                    └──────┬───────┘
                           │
                 ┌─────────┴──────────┐
                 │                    │
          有追问  │                    │  无追问
                 ▼                    ▼
        ┌─────────────────┐   ┌──────────────┐
        │  human_in_loop   │   │ merge_issues │
        │  (interrupt)     │   └──────┬───────┘
        │  等待用户回复     │          │
        └────────┬────────┘   ┌──────▼───────┐
                 │            │    END       │
                 │            └──────────────┘
        用户回复后继续
                 │
                 ▼
        ┌─────────────────┐
        │  re_review      │  基于用户回答追加审查
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │  check_round    │  检查是否达到最大轮次
        └────────┬────────┘
                 │
        ┌────────┴────────┐
        │                 │
  未达上限│                 │已达上限
        ▼                 ▼
  回到 check_follow   ┌──────────────┐
                     │ merge_issues │
                     └──────┬───────┘
                            │
                     ┌──────▼───────┐
                     │    END       │
                     └──────────────┘
```

**关键实现：使用 LangGraph `interrupt` 机制**

LangGraph 原生支持 Human-in-the-loop，通过 `interrupt` 暂停图执行，等待外部输入后恢复：

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

def build_autonomous_graph() -> StateGraph:
    graph = StateGraph(ReviewState)
    checkpointer = MemorySaver()  # 持久化 State 以支持 interrupt

    # 添加节点
    graph.add_node("parse_prd", parse_prd_node)
    graph.add_node("pm_review", pm_review_node)
    graph.add_node("dev_review", dev_review_node)
    graph.add_node("qa_review", qa_review_node)
    graph.add_node("check_follow", check_follow_node)
    graph.add_node("human_in_loop", human_in_loop_node)
    graph.add_node("re_review", re_review_node)
    graph.add_node("check_round", check_round_node)
    graph.add_node("merge_issues", merge_issues_node)

    graph.set_entry_point("parse_prd")

    # parse → 三Agent并行
    graph.add_edge("parse_prd", "pm_review")
    graph.add_edge("parse_prd", "dev_review")
    graph.add_edge("parse_prd", "qa_review")

    # 三Agent → check_follow
    graph.add_edge("pm_review", "check_follow")
    graph.add_edge("dev_review", "check_follow")
    graph.add_edge("qa_review", "check_follow")

    # 条件分支：有追问 → human_in_loop，无追问 → merge
    graph.add_conditional_edges(
        "check_follow",
        lambda state: "human_in_loop" if state["pending_follow_ups"] else "merge_issues"
    )

    # human_in_loop → re_review（用户回复后恢复执行）
    graph.add_edge("human_in_loop", "re_review")

    # re_review → check_round
    graph.add_edge("re_review", "check_round")

    # 条件分支：未达上限 → check_follow，已达上限 → merge
    graph.add_conditional_edges(
        "check_round",
        lambda state: "check_follow" if state["current_round"] < state["project_config"]["max_review_rounds_autonomous"] else "merge_issues"
    )

    # merge → END
    graph.add_edge("merge_issues", END)

    return graph.compile(checkpointer=checkpointer)
```

### 9.4 关键节点实现说明

#### parse_prd 节点

```python
def parse_prd_node(state: ReviewState) -> dict:
    """解析PRD：提取结构、识别图片"""
    prd_content = state["prd_content"]
    prd_images = state["prd_images"]

    # 1. 解析PRD章节结构
    prd_structure = parse_prd_structure(prd_content)

    # 2. 对未识别的图片调用多模态模型
    for img in prd_images:
        if img["recognition_status"] == "PENDING":
            try:
                result = call_multimodal_model(
                    image_url=img["local_path"],
                    prompt="请描述这张图片的内容，重点关注：流程、状态、数据流向、关键节点。以结构化文本输出。"
                )
                img["recognition_status"] = "COMPLETED"
                img["recognition_result"] = result
            except Exception:
                img["recognition_status"] = "FAILED"
                img["recognition_result"] = None

    # 3. 将图片识别结果注入 PRD 文本（供文本模型使用）
    enriched_content = enrich_prd_with_image_text(prd_content, prd_images)

    return {
        "prd_structure": prd_structure,
        "prd_images": prd_images,
        "prd_content": enriched_content,
        "agent_statuses": {"PM_REVIEW": "PENDING", "DEV_REVIEW": "PENDING", "QA_REVIEW": "PENDING"},
        "issues": [],
        "follow_ups": [],
        "current_round": 1
    }
```

#### human_in_loop 节点（核心：interrupt 机制）

```python
from langgraph.types import interrupt

def human_in_loop_node(state: ReviewState) -> dict:
    """暂停执行，等待用户回复追问"""
    pending = state["pending_follow_ups"]

    # 关键：interrupt 暂停图执行，将 State 保存到 Checkpoint
    # 前端收到 FOLLOW_UP_CREATED WebSocket 消息后展示追问面板
    # 用户回复后，后端调用 graph.update_state() 恢复执行
    user_response = interrupt({
        "type": "FOLLOW_UP",
        "pending_follow_ups": pending,
        "message": f"Agent 提出了 {len(pending)} 个追问，请回复后继续审查"
    })

    # 用户回复后恢复执行
    return {
        "user_answers": user_response.get("answers", []),
        "pending_follow_ups": []  # 清空待回复
    }
```

**恢复执行的 API 调用**：

```python
# 当用户通过 POST /follow-ups/{id}/answer 回复追问时
def handle_follow_up_answer(session_id: str, follow_up_id: str, answer: str, action: str):
    # 1. 更新数据库中的追问状态
    update_follow_up_in_db(session_id, follow_up_id, answer, action)

    # 2. 恢复 LangGraph 图执行
    graph = get_autonomous_graph()
    # 构建 Command 恢复 interrupt
    graph.update_state(
        config={"configurable": {"thread_id": session_id}},
        values={"user_answers": [{"follow_up_id": follow_up_id, "answer": answer, "action": action}]},
        as_node="human_in_loop"
    )
    # 继续执行
    graph.invoke(None, config={"configurable": {"thread_id": session_id}})
```

#### check_follow 节点

```python
def check_follow_node(state: ReviewState) -> dict:
    """从本轮审查结果中提取追问"""
    new_issues = state["issues"]  # 本轮新产生的问题
    pending_follow_ups = []

    # 从 Agent 输出中提取追问（Agent 输出中 type=FOLLOW_UP 的项）
    for issue in new_issues:
        if issue.get("type") == "FOLLOW_UP":
            pending_follow_ups.append(issue)

    # 限制追问数量
    max_follow_ups = state["project_config"]["max_follow_up_questions"]
    pending_follow_ups = pending_follow_ups[:max_follow_ups]

    return {"pending_follow_ups": pending_follow_ups}
```

#### re_review 节点

```python
def re_review_node(state: ReviewState) -> dict:
    """基于用户回答追加审查"""
    user_answers = state["user_answers"]

    # 将用户回答注入 PRD 文本
    enriched_content = state["prd_content"] + "\n\n## 用户补充信息\n"
    for answer in user_answers:
        enriched_content += f"- {answer['answer']}\n"

    # 基于补充信息重新审查（可选择性只审查相关章节）
    new_issues = []
    for agent_name in ["PM_REVIEW", "DEV_REVIEW", "QA_REVIEW"]:
        agent_issues = run_single_agent(
            agent_name=agent_name,
            prd_content=enriched_content,
            focus_answers=user_answers,
            round=state["current_round"] + 1
        )
        new_issues.extend(agent_issues)

    return {
        "prd_content": enriched_content,
        "issues": new_issues,
        "current_round": state["current_round"] + 1,
        "pending_follow_ups": []
    }
```

### 9.5 循环保护机制

| 保护项 | 限制值 | 实现位置 |
|--------|--------|---------|
| 最大审查轮次 | 确定性=1，自主=3 | `check_round` 节点条件判断 |
| 最大追问次数 | 5（可配置） | `check_follow` 节点截断 |
| 单Agent节点超时 | 120s | 节点内 `asyncio.wait_for` |
| 全局会话超时 | 确定性=5min，自主=10min | FastAPI 后台定时检查 |
| 单轮最大问题数 | 30/Agent | Agent Prompt 约束 + 代码截断 |

### 9.6 确定性 vs 自主模式对比

| 维度 | 确定性模式 | 自主模式 |
|------|-----------|---------|
| 图结构 | 线性：parse → 3agents → merge → end | 循环：parse → 3agents → check_follow → human → re_review → check_round → (循环/merge) |
| Checkpointer | 不需要 | 必须（MemorySaver 或 PostgreSQL） |
| interrupt | 不使用 | `human_in_loop` 节点使用 `interrupt()` |
| 审查轮次 | 固定1轮 | 最多3轮（可配置） |
| 追问 | 无 | 有，最多5次 |
| 并发模型 | 三Agent并行 | 三Agent并行 + 追问后可选择仅相关Agent重审 |
| 执行时长 | 1-3分钟 | 3-10分钟（含等待用户回复时间） |

### 9.7 Checkpointer 选型

| 方案 | 适用阶段 | 说明 |
|------|---------|------|
| MemorySaver | MVP | 内存存储，进程重启丢失（MVP可接受） |
| PostgreSQL (langgraph-checkpoint-postgres) | Phase 2 | 持久化，支持进程重启恢复 |

MVP 使用 MemorySaver。如果 MVP 部署为单实例，进程重启概率低，可接受。Phase 2 切换 PostgreSQL Checkpointer。

---

## 十、MVP 部署环境

### 10.1 MVP 部署策略：Docker Compose 单机

**决策**：MVP 阶段使用 Docker Compose 单机部署，不引入 K8s。

**理由**：

| 维度 | Docker Compose | K8s |
|------|---------------|-----|
| 学习成本 | 低 | 高 |
| 运维复杂度 | 低 | 高 |
| MVP 适用性 | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 多实例扩展 | ❌ | ✅ |
| 自愈能力 | ❌（需手动） | ✅ |
| 滚动更新 | ❌ | ✅ |
| MVP 阶段必要性 | 足够 | 过度 |

### 10.2 Docker Compose 服务清单

```yaml
# docker-compose.yml
version: "3.8"

services:
  # ---- 前端 ----
  web:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://api:8000
      - NEXT_PUBLIC_WS_URL=ws://api:8000
    depends_on:
      - api
    restart: unless-stopped

  # ---- 后端 API ----
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://revyou:revyou_pass@postgres:5432/revyou
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET=${JWT_SECRET}
      - TAPD_API_BASE=https://api.tapd.cn
      - UPLOAD_DIR=/data/uploads
      - LLM_DEEPSEEK_API_KEY=${LLM_DEEPSEEK_API_KEY}
      - LLM_QWEN_API_KEY=${LLM_QWEN_API_KEY}
      - LLM_OPENAI_API_KEY=${LLM_OPENAI_API_KEY}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
    volumes:
      - upload_data:/data/uploads
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  # ---- 后台任务 Worker（Agent 执行）----
  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: python -m worker.main
    environment:
      - DATABASE_URL=postgresql://revyou:revyou_pass@postgres:5432/revyou
      - REDIS_URL=redis://redis:6379/0
      - LLM_DEEPSEEK_API_KEY=${LLM_DEEPSEEK_API_KEY}
      - LLM_QWEN_API_KEY=${LLM_QWEN_API_KEY}
      - LLM_OPENAI_API_KEY=${LLM_OPENAI_API_KEY}
      - UPLOAD_DIR=/data/uploads
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
    volumes:
      - upload_data:/data/uploads
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  # ---- PostgreSQL ----
  postgres:
    image: postgres:15-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=revyou
      - POSTGRES_PASSWORD=revyou_pass
      - POSTGRES_DB=revyou
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./backend/sql/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U revyou"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # ---- Redis（缓存 + 队列）----
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    restart: unless-stopped

volumes:
  pg_data:
  redis_data:
  upload_data:
```

### 10.3 服务职责说明

| 服务 | 职责 | 技术栈 | 端口 |
|------|------|--------|------|
| web | 前端页面服务 | Next.js 14 + Ant Design | 3000 |
| api | REST API + WebSocket | FastAPI + uvicorn | 8000 |
| worker | Agent 执行引擎（LangGraph） | Python 3.11 + LangGraph | 无外部端口 |
| postgres | 主数据库 | PostgreSQL 15 | 5432 |
| redis | 缓存 + 任务队列 + WebSocket pub/sub | Redis 7 | 6379 |

### 10.4 为什么拆分 api 和 worker

| 方案 | 优点 | 缺点 |
|------|------|------|
| api + worker 合并 | 部署简单 | Agent 执行阻塞 API 请求；无法独立扩缩 |
| api + worker 拆分 ✅ | API 响应快；Worker 可独立扩展；故障隔离 | 多一个服务进程 |

**拆分方案**：

- `api`：仅处理 HTTP 请求、WebSocket 连接、轻量查询。Agent 审查请求通过 Redis 队列下发给 `worker`
- `worker`：从 Redis 队列消费任务，执行 LangGraph 图，结果写回数据库。通过 Redis pub/sub 通知 `api` 推送 WebSocket 消息

**通信流程**：

```
用户请求 → API → Redis RPush(review_task) → Worker BLPop → 执行LangGraph
                                                          │
                                                          ├─ 写入DB（问题/状态）
                                                          └─ Redis Publish(ws_event) → API → WebSocket → 前端
```

### 10.5 环境变量与密钥管理

MVP 使用 `.env` 文件管理，不引入 Vault 等密钥管理服务。

```bash
# .env（示例，实际部署时替换）
JWT_SECRET=your-jwt-secret-at-least-32-chars
ENCRYPTION_KEY=your-aes256-encryption-key-32bytes

LLM_DEEPSEEK_API_KEY=sk-xxx
LLM_QWEN_API_KEY=sk-xxx
LLM_OPENAI_API_KEY=sk-xxx

TAPD_API_BASE=https://api.tapd.cn
```

**安全要求**：

| 项目 | 要求 |
|------|------|
| .env 文件权限 | `chmod 600 .env` |
| .gitignore | 必须包含 `.env` |
| 密钥轮换 | 至少每 90 天更换一次 JWT_SECRET |
| TAPD Token 存储 | AES-256 加密后存入数据库，密钥从 ENCRYPTION_KEY 读取 |

### 10.6 服务器最低配置

| 项目 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 4 核 | 8 核 |
| 内存 | 8 GB | 16 GB |
| 磁盘 | 50 GB SSD | 100 GB SSD |
| 带宽 | 5 Mbps | 10 Mbps |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

**内存估算**：

| 服务 | 预估内存 |
|------|---------|
| Next.js | 512 MB |
| FastAPI (api) | 512 MB |
| Python Worker (LangGraph) | 1-2 GB（含LLM调用缓冲） |
| PostgreSQL | 1 GB |
| Redis | 256 MB |
| 系统 + Docker | 1 GB |
| **合计** | **4.3-5.3 GB** |

### 10.7 初始化脚本

```bash
#!/bin/bash
# deploy.sh — MVP 一键部署脚本

set -e

echo "=== AI需求评审Agent MVP 部署 ==="

# 1. 检查 Docker & Docker Compose
command -v docker >/dev/null 2>&1 || { echo "错误：未安装 Docker"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || docker compose version >/dev/null 2>&1 || { echo "错误：未安装 Docker Compose"; exit 1; }

# 2. 检查 .env 文件
if [ ! -f .env ]; then
    echo "错误：未找到 .env 文件，请基于 .env.example 创建"
    exit 1
fi

# 3. 创建数据目录
mkdir -p /data/uploads

# 4. 构建镜像
echo "正在构建镜像..."
docker compose build

# 5. 启动服务
echo "正在启动服务..."
docker compose up -d

# 6. 等待 PostgreSQL 就绪
echo "等待数据库启动..."
sleep 10

# 7. 执行数据库迁移
docker compose exec api python -m alembic upgrade head

# 8. 创建默认管理员
docker compose exec api python -m scripts.create_admin

echo "=== 部署完成 ==="
echo "前端访问地址：http://localhost:3000"
echo "API 文档地址：http://localhost:8000/docs"
```

### 10.8 Phase 2 升级路径：K8s

MVP 验证完成后，升级到 K8s 的路径：

| 组件 | Docker Compose → K8s 映射 |
|------|--------------------------|
| web | Deployment + Service + Ingress |
| api | Deployment + Service + HPA |
| worker | Deployment + HPA |
| postgres | StatefulSet + PVC 或 云托管 RDS |
| redis | StatefulSet + PVC 或 云托管 Redis |
| 文件存储 | PV/PVC → MinIO (S3兼容) |
| 密钥管理 | .env → K8s Secret / External Secrets |
| 配置管理 | .env → ConfigMap |

---

## 附录：技术补充文档与PRD的映射关系

| 本文档章节 | 对应PRD V1.1章节 | 补充内容 |
|-----------|-----------------|---------|
| 一、REST API | 四、核心业务流程 + 十二、核心数据模型 | 接口端点、请求响应Schema |
| 二、页面结构 | 无（PRD未定义） | 页面清单、路由、工作台布局 |
| 三、实时交互 | 五、5.2 自主Agent模式 | WebSocket方案、追问交互UI |
| 四、Agent Prompt | 四、4.3 Agent多角色预审 | 三个Agent的System Prompt |
| 五、数据库DDL | 十二、核心数据模型 | 完整建表语句、JSON结构定义 |
| 六、UI组件库 | 十七、17.2 技术选型 | 具体UI框架和依赖选择 |
| 七、JSON解析策略 | 四、4.3 Agent多角色预审 + 七、AI模型与多模态能力 | 三层防御解析策略、Pydantic校验模型、重试降级方案 |
| 八、文件存储方案 | 四、4.2 Step1导入需求 + 十二、核心数据模型 | 存储选型、目录结构、生命周期管理、解析技术栈 |
| 九、LangGraph图结构 | 五、Agent工作模式 + 十七、技术架构 | State定义、确定性/自主双图结构、interrupt机制、循环保护 |
| 十、MVP部署环境 | 十七、17.1 技术架构 | Docker Compose配置、服务拆分、环境变量、升级路径 |

---

> **文档结束**
> 本文档为AI需求评审Agent PRD V1.1的技术补充文档（V1.1），与PRD V1.1配套使用。开发阶段如需调整接口设计或数据库Schema，需经技术负责人与产品负责人双方确认。
