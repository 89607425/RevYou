"""Notifications API: in-app notification management."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    read: bool = Query(default=None),
    type: str = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Notification).where(Notification.user_id == current_user.user_id)
    count_query = select(func.count()).select_from(Notification).where(
        Notification.user_id == current_user.user_id
    )

    if read is not None:
        query = query.where(Notification.is_read == read)
        count_query = count_query.where(Notification.is_read == read)
    if type:
        query = query.where(Notification.type == type)
        count_query = count_query.where(Notification.type == type)

    total = (await db.execute(count_query)).scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Notification.created_at.desc()).offset(offset).limit(page_size)
    )
    notifications = result.scalars().all()

    items = [
        {
            "notification_id": n.notification_id,
            "type": n.type,
            "title": n.title,
            "content": n.content,
            "related_session_id": n.related_session_id,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifications
    ]

    return {"code": 0, "data": {"total": total, "items": items}}


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.notification_id == notification_id,
            Notification.user_id == current_user.user_id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification.is_read = True
    await db.commit()
    return {"code": 0, "data": {"notification_id": notification_id, "is_read": True}}


@router.patch("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.user_id, Notification.is_read == False)
        .values(is_read=True)
    )
    await db.commit()
    return {"code": 0, "data": {"message": "All notifications marked as read"}}


async def create_notification(
    db: AsyncSession,
    user_id: str,
    type: str,
    title: str,
    content: str,
    session_id: str = None,
):
    """Utility function to create a notification."""
    notification = Notification(
        notification_id=f"NOTIF-{uuid.uuid4().hex[:12].upper()}",
        user_id=user_id,
        type=type,
        title=title,
        content=content,
        related_session_id=session_id,
        is_read=False,
    )
    db.add(notification)
    await db.flush()
    return notification
