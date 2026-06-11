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
