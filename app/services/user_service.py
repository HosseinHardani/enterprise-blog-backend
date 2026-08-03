"""
Business logic for user profile management.
"""

import uuid
from datetime import UTC

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.exceptions.custom import AlreadyExistsError, ForbiddenError, InvalidCredentialsError, NotFoundError
from app.models.user import User, UserRole
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)

    async def get_by_id_or_404(self, user_id: uuid.UUID) -> User:
        user = await self.users.get_by_id(user_id)
        if user is None or user.is_deleted:
            raise NotFoundError("User not found")
        return user

    async def get_by_username_or_404(self, username: str) -> User:
        user = await self.users.get_by_username(username)
        if user is None or user.is_deleted:
            raise NotFoundError("User not found")
        return user

    async def update_profile(self, user: User, full_name: str | None, bio: str | None) -> User:
        update_kwargs = {}
        if full_name is not None:
            update_kwargs["full_name"] = full_name
        if bio is not None:
            update_kwargs["bio"] = bio
        updated = await self.users.update(user, **update_kwargs)
        await self.db.commit()
        return updated

    async def update_profile_image(self, user: User, image_url: str) -> User:
        updated = await self.users.update(user, profile_image_url=image_url)
        await self.db.commit()
        return updated

    async def change_email(self, user: User, new_email: str, current_password: str) -> User:
        if not verify_password(current_password, user.hashed_password):
            raise InvalidCredentialsError("Current password is incorrect")
        existing = await self.users.get_by_email(new_email)
        if existing and existing.id != user.id:
            raise AlreadyExistsError("This email is already in use")

        updated = await self.users.update(user, email=new_email, is_email_verified=False)
        await self.db.commit()
        return updated

    async def soft_delete_account(self, user: User) -> None:
        from datetime import datetime

        user.is_deleted = True
        user.is_active = False
        user.deleted_at = datetime.now(UTC)
        await self.refresh_tokens.revoke_all_for_user(user.id)
        await self.db.commit()

    async def update_role(self, actor: User, target_user_id: uuid.UUID, new_role: UserRole) -> User:
        if actor.role != UserRole.ADMIN:
            raise ForbiddenError("Only administrators can change user roles")
        target = await self.get_by_id_or_404(target_user_id)
        updated = await self.users.update(target, role=new_role)
        await self.db.commit()
        return updated
