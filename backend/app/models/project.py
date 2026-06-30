from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    project_id = Column(String(32), primary_key=True)
    name = Column(String(128), nullable=False)
    tapd_project_id = Column(String(32))
    tapd_api_user = Column(String(128))
    tapd_token_encrypted = Column(String)
    config = Column(JSON, nullable=False)
    status = Column(String(16), nullable=False, default="ACTIVE")
    created_by = Column(String(32), ForeignKey("users.user_id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(32), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(32), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    role = Column(String(16), nullable=False, default="PM")
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="members")
