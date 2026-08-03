"""
FastAPI dependencies for authentication and role-based authorization.
"""

import uuid

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose.exceptions import ExpiredSignatureError, JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenType, decode_token
from app.database.session import get_db
from app.dependencies.redis_client import get_redis
from app.exceptions.custom import AccountInactiveError, ForbiddenError, TokenError, UnauthorizedError
from app.models.user import User, UserRole
from app.repositories.user import UserRepository

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    if not token:
        raise UnauthorizedError("Not authenticated")

    try:
        payload = decode_token(token)
    except ExpiredSignatureError as err:
        raise TokenError("Access token has expired") from err
    except JWTError as err:
        raise TokenError("Could not validate credentials") from err

    if payload.get("type") != TokenType.ACCESS.value:
        raise TokenError("Invalid token type")

    jti = payload.get("jti")

    if jti and await redis.get(f"blacklist:access:{jti}"):
        raise TokenError("Token has been revoked")

    user_id = payload.get("sub")

    if user_id is None:
        raise TokenError("Malformed token")

    repo = UserRepository(db)

    user = await repo.get_by_id(uuid.UUID(user_id))

    if user is None or user.is_deleted:
        raise UnauthorizedError("User no longer exists")

    if not user.is_active:
        raise AccountInactiveError()

    return user


async def get_current_active_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_email_verified:
        from app.exceptions.custom import AccountNotVerifiedError

        raise AccountNotVerifiedError()

    return current_user


async def get_optional_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User | None:
    if not token:
        return None

    try:
        return await get_current_user(
            token=token,
            db=db,
            redis=redis,
        )
    except Exception:
        return None


def require_roles(*allowed_roles: UserRole):

    async def _checker(
        current_user: User = Depends(get_current_user),
    ) -> User:

        if current_user.role not in allowed_roles:
            raise ForbiddenError(
                f"This action requires one of the following roles: "
                f"{', '.join(r.value for r in allowed_roles)}"
            )

        return current_user

    return _checker


require_admin = require_roles(UserRole.ADMIN)

require_editor_or_admin = require_roles(
    UserRole.ADMIN,
    UserRole.EDITOR,
)
