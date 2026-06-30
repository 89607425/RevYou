from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Numeric, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ReviewSession(Base):
    __tablename__ = "review_sessions"

    session_id = Column(String(32), primary_key=True)
    project_id = Column(String(32), ForeignKey("projects.project_id"), nullable=False)
    prd_content = Column(Text, nullable=False)
    prd_source = Column(String(16), nullable=False)
    prd_structure = Column(JSON)
    prd_images = Column(JSON)
    tapd_story_id = Column(String(32))
    agent_mode = Column(String(16), nullable=False, default="DETERMINISTIC")
    status = Column(String(16), nullable=False, default="RUNNING")
    initiator_id = Column(String(32), ForeignKey("users.user_id"), nullable=False)
    agent_results = Column(JSON)
    follow_up_questions = Column(JSON)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    issues = relationship("ReviewIssue", back_populates="session", cascade="all, delete-orphan")


class ReviewIssue(Base):
    __tablename__ = "review_issues"

    issue_id = Column(String(32), primary_key=True)
    session_id = Column(String(32), ForeignKey("review_sessions.session_id", ondelete="CASCADE"), nullable=False)
    source_agent = Column(String(16), nullable=False)
    issue_type = Column(String(32), nullable=False)
    severity = Column(String(8), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    suggestion = Column(Text)
    prd_section = Column(String(200))
    prd_quote = Column(Text)
    image_ref = Column(String(200))
    confidence = Column(Numeric(3, 2), nullable=False, default=0.80)
    confidence_label = Column(String(8), nullable=False, default="HIGH")
    status = Column(String(20), nullable=False, default="OPEN")
    review_round = Column(Integer, nullable=False, default=1)
    cross_review_tags = Column(JSON)
    resolved_by = Column(String(32), ForeignKey("users.user_id"))
    resolution_note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    session = relationship("ReviewSession", back_populates="issues")
    comments = relationship("IssueComment", back_populates="issue", cascade="all, delete-orphan")


class IssueComment(Base):
    __tablename__ = "issue_comments"

    comment_id = Column(String(32), primary_key=True)
    issue_id = Column(String(32), ForeignKey("review_issues.issue_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(32), ForeignKey("users.user_id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    issue = relationship("ReviewIssue", back_populates="comments")
