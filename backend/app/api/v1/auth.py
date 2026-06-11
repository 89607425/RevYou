from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.core.config import settings
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest
from app.schemas.common import APIResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=APIResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User disabled")

    token = create_access_token(user.user_id)
    expires_at = (datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)).isoformat() + "Z"

    user.last_login_at = datetime.utcnow()
    await db.flush()

    return APIResponse(data=TokenResponse(
        token=token,
        expires_at=expires_at,
        user={"user_id": user.user_id, "username": user.username, "display_name": user.display_name, "role": user.role}
    ).model_dump())


@router.post("/refresh", response_model=APIResponse)
async def refresh_token(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    from app.core.security import decode_token
    payload = decode_token(req.token)
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    token = create_access_token(user.user_id)
    expires_at = (datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)).isoformat() + "Z"

    return APIResponse(data=TokenResponse(
        token=token,
        expires_at=expires_at,
        user={"user_id": user.user_id, "username": user.username, "display_name": user.display_name, "role": user.role}
    ).model_dump())


@router.get("/me", response_model=APIResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return APIResponse(data={
        "user_id": current_user.user_id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "role": current_user.role,
        "email": current_user.email,
    })
