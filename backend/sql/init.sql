-- ============================================
-- AI需求评审Agent 数据库 Schema
-- MySQL 8.0+
-- ============================================

CREATE TABLE users (
    user_id         VARCHAR(32) PRIMARY KEY,
    username        VARCHAR(64) NOT NULL UNIQUE,
    password_hash   VARCHAR(256) NOT NULL,
    display_name    VARCHAR(64) NOT NULL,
    email           VARCHAR(128),
    role            VARCHAR(16) NOT NULL DEFAULT 'PM',
    status          VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    last_login_at   TIMESTAMP NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role ON users(role);

CREATE TABLE projects (
    project_id          VARCHAR(32) PRIMARY KEY,
    name                VARCHAR(128) NOT NULL,
    tapd_project_id     VARCHAR(32),
    tapd_api_user       VARCHAR(128),
    tapd_token_encrypted TEXT,
    config              JSON NOT NULL,
    status              VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    created_by          VARCHAR(32),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_projects_tapd ON projects(tapd_project_id);

CREATE TABLE project_members (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    project_id  VARCHAR(32) NOT NULL,
    user_id     VARCHAR(32) NOT NULL,
    role        VARCHAR(16) NOT NULL DEFAULT 'PM',
    joined_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, user_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_pm_project ON project_members(project_id);
CREATE INDEX idx_pm_user ON project_members(user_id);

CREATE TABLE review_sessions (
    session_id      VARCHAR(32) PRIMARY KEY,
    project_id      VARCHAR(32) NOT NULL,
    prd_content     TEXT NOT NULL,
    prd_source      VARCHAR(16) NOT NULL,
    prd_structure   JSON,
    prd_images      JSON,
    tapd_story_id   VARCHAR(32),
    agent_mode      VARCHAR(16) NOT NULL DEFAULT 'DETERMINISTIC',
    status          VARCHAR(16) NOT NULL DEFAULT 'RUNNING',
    initiator_id    VARCHAR(32) NOT NULL,
    agent_results   JSON,
    follow_up_questions JSON,
    started_at      TIMESTAMP NULL,
    completed_at    TIMESTAMP NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id),
    FOREIGN KEY (initiator_id) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_sessions_project ON review_sessions(project_id);
CREATE INDEX idx_sessions_status ON review_sessions(status);
CREATE INDEX idx_sessions_initiator ON review_sessions(initiator_id);
CREATE INDEX idx_sessions_created ON review_sessions(created_at DESC);

CREATE TABLE review_issues (
    issue_id        VARCHAR(32) PRIMARY KEY,
    session_id      VARCHAR(32) NOT NULL,
    source_agent    VARCHAR(16) NOT NULL,
    issue_type      VARCHAR(32) NOT NULL,
    severity        VARCHAR(8) NOT NULL,
    title           VARCHAR(200) NOT NULL,
    description     TEXT NOT NULL,
    suggestion      TEXT,
    prd_section     VARCHAR(200),
    prd_quote       TEXT,
    image_ref       VARCHAR(200),
    cross_review_tags JSON,
    confidence      DECIMAL(3,2) NOT NULL DEFAULT 0.80,
    confidence_label VARCHAR(8) NOT NULL DEFAULT 'HIGH',
    status          VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    review_round    INT NOT NULL DEFAULT 1,
    resolved_by     VARCHAR(32),
    resolution_note TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES review_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (resolved_by) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_issues_session ON review_issues(session_id);
CREATE INDEX idx_issues_agent ON review_issues(source_agent);
CREATE INDEX idx_issues_severity ON review_issues(severity);
CREATE INDEX idx_issues_status ON review_issues(status);
CREATE INDEX idx_issues_type ON review_issues(issue_type);
CREATE INDEX idx_issues_confidence ON review_issues(confidence);
CREATE INDEX idx_issues_session_severity ON review_issues(session_id, severity);

CREATE TABLE issue_comments (
    comment_id      VARCHAR(32) PRIMARY KEY,
    issue_id        VARCHAR(32) NOT NULL,
    user_id         VARCHAR(32) NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (issue_id) REFERENCES review_issues(issue_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_comments_issue ON issue_comments(issue_id);
CREATE INDEX idx_comments_user ON issue_comments(user_id);

CREATE TABLE audit_logs (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id         VARCHAR(32),
    project_id      VARCHAR(32),
    session_id      VARCHAR(32),
    action          VARCHAR(64) NOT NULL,
    detail          JSON,
    ip_address      VARCHAR(45),
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_project ON audit_logs(project_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);

CREATE TABLE notifications (
    notification_id  VARCHAR(32) PRIMARY KEY,
    user_id          VARCHAR(32) NOT NULL,
    type             VARCHAR(32) NOT NULL,
    title            VARCHAR(200) NOT NULL,
    content          TEXT NOT NULL,
    related_session_id VARCHAR(32),
    is_read          TINYINT(1) NOT NULL DEFAULT 0,
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_notifications_user ON notifications(user_id, is_read, created_at DESC);
CREATE INDEX idx_notifications_type ON notifications(type);

CREATE TABLE severity_change_logs (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    issue_id        VARCHAR(32) NOT NULL,
    old_severity    VARCHAR(8) NOT NULL,
    new_severity    VARCHAR(8) NOT NULL,
    reason          TEXT NOT NULL,
    changed_by      VARCHAR(32) NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (issue_id) REFERENCES review_issues(issue_id),
    FOREIGN KEY (changed_by) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_severity_change_issue ON severity_change_logs(issue_id);
