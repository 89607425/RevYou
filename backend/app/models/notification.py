from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(String(32), primary_key=True)
    user_id = Column(String(32), ForeignKey("users.user_id"), nullable=False)
    type = Column(String(32), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    related_session_id = Column(String(32))
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
