"""
Business logic for authentication: registration, login, logout, token
refresh/rotation, email verification, and password reset.

Token strategy
--------------
- Access tokens are short-lived JWTs (default 15 min). They are stateless
  but individually revocable: on logout we add their `jti` to a Redis
  blacklist with a TTL equal to their remaining lifetime.
- Refresh tokens are long-lived JWTs (default 30 days) whose `jti` is also
  persisted in the `refresh_tokens` table. This lets us revoke a single
  session, revoke *all* sessions for a user (e.g. on password change), and
  detect refresh-token reuse after rotation.
- Every refresh call rotates the refresh token (single-use refresh tokens)
  to limit the blast radius of a leaked token.
"""
import uuid
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    create_special_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.exceptions.custom import (
    AlreadyExistsError,
    InvalidCredentialsError,
    NotFoundError,
    TokenError,
)
from app.models.user import User
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository


def _dispatch_verification_email(to: str, token: str) -> None:
    try:
        from app.tasks.email_tasks import send_verification_email_task

        send_verification_email_task.delay(to=to, token=token)
    except Exception:
        # Broker unavailable (e.g. local dev without Redis/Celery running) --
        # fall back to a direct synchronous send so the flow still works.
        from app.services.email_service import build_verification_email, send_email

        subject, html = build_verification_email(token)
        send_email(to=to, subject=subject, html_body=html)


def _dispatch_password_reset_email(to: str, token: str) -> None:
    try:
        from app.tasks.email_tasks import send_password_reset_email_task

        send_password_reset_email_task.delay(to=to, token=token)
    except Exception:
        from app.services.email_service import build_password_reset_email, send_email

        subject, html = build_password_reset_email(token)
        send_email(to=to, subject=subject, html_body=html)


class AuthService:
    def __init__(self, db: AsyncSession, redis: Redis | None = None):
        self.db = db
        self.redis = redis
        self.users = UserRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)

    # --- Registration -----------------------------------------------------

    async def register(self, email: str, username: str, password: str, full_name: str | None) -> User:
        if await self.users.get_by_email(email):
            raise AlreadyExistsError("An account with this email already exists")
        if await self.users.get_by_username(username):
            raise AlreadyExistsError("This username is already taken")

        user = await self.users.create(
            email=email,
            username=username,
            hashed_password=hash_password(password),
            full_name=full_name,
        )
        await self.db.commit()

        token, _, _ = create_special_token(
            subject=str(user.id),
            token_type=TokenType.EMAIL_VERIFICATION,
            expires_delta=timedelta(hours=24),
        )
        _dispatch_verification_email(user.email, token)

        return user

    # --- Login / logout -----------------------------------------------------

    async def login(
        self, identifier: str, password: str, user_agent: str | None, ip_address: str | None
    ) -> tuple[User, str, str, datetime]:
        """Returns (user, access_token, refresh_token, refresh_expires_at)."""
        user = await self.users.get_by_email_or_username(identifier)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Incorrect email/username or password")
        if user.is_deleted or not user.is_active:
            raise InvalidCredentialsError("This account is inactive")

        access_token, _, _ = create_access_token(subject=str(user.id), role=user.role.value)
        refresh_token, refresh_jti, refresh_exp = create_refresh_token(subject=str(user.id))

        await self.refresh_tokens.create(
            user_id=user.id,
            jti=refresh_jti,
            expires_at=refresh_exp,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await self.db.commit()
        return user, access_token, refresh_token, refresh_exp

    async def logout(self, access_token_payload: dict, refresh_token: str | None) -> None:
        # Blacklist the current access token for the remainder of its life.
        jti = access_token_payload.get("jti")
        exp = access_token_payload.get("exp")
        if jti and exp:
            ttl = max(int(exp - datetime.now(timezone.utc).timestamp()), 1)
            await self.redis.set(f"blacklist:access:{jti}", "1", ex=ttl)

        if refresh_token:
            try:
                payload = decode_token(refresh_token)
                stored = await self.refresh_tokens.get_by_jti(payload.get("jti", ""))
                if stored:
                    stored.revoked = True
                    await self.db.flush()
                    await self.db.commit()
            except Exception:
                pass  # Already invalid/expired -- nothing to revoke.

    # --- Token refresh -----------------------------------------------------

    async def refresh_access_token(
        self, refresh_token: str, user_agent: str | None, ip_address: str | None
    ) -> tuple[str, str, datetime]:
        """Rotates the refresh token. Returns (access_token, new_refresh_token, new_refresh_expires_at)."""
        try:
            payload = decode_token(refresh_token)
        except Exception:
            raise TokenError("Invalid or expired refresh token")

        if payload.get("type") != TokenType.REFRESH.value:
            raise TokenError("Invalid token type")

        stored = await self.refresh_tokens.get_by_jti(payload.get("jti", ""))
        if stored is None:
            raise TokenError("Refresh token not recognized")
        if stored.revoked:
            # Possible token reuse/theft -- revoke the whole session family defensively.
            await self.refresh_tokens.revoke_all_for_user(stored.user_id)
            await self.db.commit()
            raise TokenError("Refresh token has already been used")
        if stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise TokenError("Refresh token has expired")

        user = await self.users.get_by_id(stored.user_id)
        if user is None or not user.is_active or user.is_deleted:
            raise TokenError("User no longer active")

        # Rotate: revoke the old one, issue a new one.
        stored.revoked = True
        access_token, _, _ = create_access_token(subject=str(user.id), role=user.role.value)
        new_refresh_token, new_jti, new_exp = create_refresh_token(subject=str(user.id))
        await self.refresh_tokens.create(
            user_id=user.id, jti=new_jti, expires_at=new_exp, user_agent=user_agent, ip_address=ip_address
        )
        await self.db.commit()
        return access_token, new_refresh_token, new_exp

    # --- Email verification -----------------------------------------------------

    async def verify_email(self, token: str) -> None:
        try:
            payload = decode_token(token)
        except Exception:
            raise TokenError("Invalid or expired verification token")
        if payload.get("type") != TokenType.EMAIL_VERIFICATION.value:
            raise TokenError("Invalid token type")

        user = await self.users.get_by_id(uuid.UUID(payload["sub"]))
        if user is None:
            raise NotFoundError("User not found")
        user.is_email_verified = True
        await self.db.commit()

    async def resend_verification(self, email: str) -> None:
        user = await self.users.get_by_email(email)
        if user is None or user.is_email_verified:
            return  # Don't leak whether the email exists.
        token, _, _ = create_special_token(
            subject=str(user.id), token_type=TokenType.EMAIL_VERIFICATION, expires_delta=timedelta(hours=24)
        )
        _dispatch_verification_email(user.email, token)

    # --- Password reset -----------------------------------------------------

    async def request_password_reset(self, email: str) -> None:
        user = await self.users.get_by_email(email)
        if user is None:
            return  # Don't leak whether the email exists.
        token, _, _ = create_special_token(
            subject=str(user.id), token_type=TokenType.PASSWORD_RESET, expires_delta=timedelta(hours=1)
        )
        _dispatch_password_reset_email(user.email, token)

    async def confirm_password_reset(self, token: str, new_password: str) -> None:
        try:
            payload = decode_token(token)
        except Exception:
            raise TokenError("Invalid or expired reset token")
        if payload.get("type") != TokenType.PASSWORD_RESET.value:
            raise TokenError("Invalid token type")

        user = await self.users.get_by_id(uuid.UUID(payload["sub"]))
        if user is None:
            raise NotFoundError("User not found")

        user.hashed_password = hash_password(new_password)
        await self.refresh_tokens.revoke_all_for_user(user.id)
        await self.db.commit()

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise InvalidCredentialsError("Current password is incorrect")
        user.hashed_password = hash_password(new_password)
        await self.refresh_tokens.revoke_all_for_user(user.id)
        await self.db.commit()
