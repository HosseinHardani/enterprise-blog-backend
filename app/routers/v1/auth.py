from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose.exceptions import JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token
from app.database.session import get_db
from app.dependencies.auth import get_current_user, oauth2_scheme
from app.dependencies.redis_client import get_redis
from app.exceptions.custom import TokenError
from app.models.user import User
from app.schemas.auth import (
    EmailVerificationRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    ResendVerificationRequest,
    TokenResponse,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserMe, UserRegister
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1/auth",
    )


@router.post(
    "/register",
    response_model=UserMe,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Creates a new account and sends an email verification link. "
    "The account can log in immediately, but some actions may require a verified email.",
)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    service = AuthService(db, None)  # redis not needed for registration
    user = await service.register(
        email=payload.email, username=payload.username, password=payload.password, full_name=payload.full_name
    )
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="OAuth2 password grant login",
    description="Standard OAuth2 password grant. Submit `username` (accepts either the account's "
    "email or its username) and `password` as form fields — this is what powers the Swagger UI "
    "'Authorize' button. Returns a short-lived access token in the response body and sets a "
    "long-lived refresh token as an HttpOnly secure cookie.",
)
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    service = AuthService(db, redis)
    user, access_token, refresh_token, _ = await service.login(
        identifier=form_data.username,
        password=form_data.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new access token",
    description="Reads the refresh token from the HttpOnly cookie, rotates it, and "
    "returns a new access token. The old refresh token becomes invalid.",
)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    print("cookies:", request.cookies)

    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)

    print("refresh:", refresh_token)
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_token:
        raise TokenError("No refresh token provided")

    service = AuthService(db, redis)
    access_token, new_refresh_token, _ = await service.refresh_access_token(
        refresh_token=refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    _set_refresh_cookie(response, new_refresh_token)
    return TokenResponse(access_token=access_token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)



@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Log out and revoke the current session",
    description="Blacklists the current access token and revokes the associated refresh token.",
)
async def logout(
    request: Request,
    response: Response,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    service = AuthService(db, redis)
    if token:
        try:
            payload = decode_token(token)
            refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
            await service.logout(access_token_payload=payload, refresh_token=refresh_token)
        except JWTError:
            pass
    response.delete_cookie(settings.REFRESH_TOKEN_COOKIE_NAME, path="/api/v1/auth")
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserMe, summary="Get the currently authenticated user")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Verify an email address using a verification token",
)
async def verify_email(payload: EmailVerificationRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db, None)
    await service.verify_email(payload.token)
    return MessageResponse(message="Email verified successfully")


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Resend the email verification link",
)
async def resend_verification(payload: ResendVerificationRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db, None)
    await service.resend_verification(payload.email)
    return MessageResponse(message="If that email exists, a verification link has been sent")


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    summary="Request a password reset email",
)
async def request_password_reset(payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db, None)
    await service.request_password_reset(payload.email)
    return MessageResponse(message="If that email exists, a password reset link has been sent")


@router.post(
    "/password-reset/confirm",
    response_model=MessageResponse,
    summary="Confirm a password reset using the emailed token",
)
async def confirm_password_reset(payload: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    service = AuthService(db, None)
    await service.confirm_password_reset(payload.token, payload.password)
    return MessageResponse(message="Password has been reset successfully")
