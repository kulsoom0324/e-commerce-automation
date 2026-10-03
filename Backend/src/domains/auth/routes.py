from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.config import get_settings
from src.sdk.database import get_db
from src.domains.auth.models import LoginMethod, User
from src.domains.auth.schemas import (
    AuthResponse,
    ForgotPasswordRequest,
    GoogleLoginRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    SignupRequest,
    UserOut,
)
from src.domains.security.jwt import create_access_token, decode_access_token, hash_password
from src.domains.auth import service as auth_service
from src.domains.security.email_service import send_email
from src.domains.security.rate_limiter import login_rate_limiter

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _client_info(request: Request):
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip, user_agent


def _decode_typed_token(token: str, expected_type: str) -> dict:
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type")
    return payload


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Naya user create karna."""
    user = await auth_service.create_local_user(db, payload)
    await auth_service.log_login(db, user, LoginMethod.LOCAL, *_client_info(request))
    token = create_access_token({"sub": str(user.id)})
    return AuthResponse(
        message="Signup successful",
        access_token=token,
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(login_rate_limiter),
):
    """Email + password login."""
    user = await auth_service.authenticate_local_user(db, payload.email, payload.password)
    await auth_service.log_login(db, user, LoginMethod.LOCAL, *_client_info(request))
    token = create_access_token({"sub": str(user.id)})
    return AuthResponse(
        message="Login successful",
        access_token=token,
        user=UserOut.model_validate(user),
    )


@router.post("/google", response_model=AuthResponse)
async def google_login(payload: GoogleLoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Google id_token se login/signup."""
    user = await auth_service.get_or_create_google_user(db, payload.id_token)
    await auth_service.log_login(db, user, LoginMethod.GOOGLE, *_client_info(request))
    token = create_access_token({"sub": str(user.id)})
    return AuthResponse(
        message="Google login successful",
        access_token=token,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(auth_service.get_current_user)):
    """Current logged-in user profile."""
    return current_user


@router.post("/send-verification", response_model=MessageResponse)
async def send_verification(current_user: User = Depends(auth_service.get_current_user)):
    """Email verification link send karna."""
    if current_user.is_verified:
        return MessageResponse(message="Email already verified")

    settings = get_settings()
    token = create_access_token(
        {"sub": str(current_user.id), "type": "email_verify"},
        expires_delta=timedelta(hours=24),
    )
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    send_email(
        current_user.email,
        "Email Verification",
        f"<p>Click to verify your email:</p><p><a href='{link}'>{link}</a></p>",
    )
    return MessageResponse(message="Verification email sent")


@router.get("/verify-email", response_model=MessageResponse)
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    """Email verification link verify karna."""
    payload = _decode_typed_token(token, "email_verify")
    stmt = select(User).where(User.id == int(payload["sub"]))
    res = await db.execute(stmt)
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_verified = True
    await db.commit()
    return MessageResponse(message="Email verified successfully")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(login_rate_limiter),
):
    """Password reset link send karna."""
    settings = get_settings()
    stmt = select(User).where(User.email == payload.email)
    res = await db.execute(stmt)
    user = res.scalars().first()

    if user:
        token = create_access_token(
            {"sub": str(user.id), "type": "reset_password"},
            expires_delta=timedelta(minutes=30),
        )
        link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        send_email(
            user.email,
            "Password Reset Request",
            f"<p>Click to reset your password:</p><p><a href='{link}'>{link}</a></p>",
        )
    return MessageResponse(message="If the email exists, a reset link has been sent")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Naya password set karna."""
    decoded = _decode_typed_token(payload.token, "reset_password")
    stmt = select(User).where(User.id == int(decoded["sub"]))
    res = await db.execute(stmt)
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return MessageResponse(message="Password successfully changed")
