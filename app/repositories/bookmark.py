import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.bookmark import Bookmark
from app.models.like import PostLike
from app.repositories.base import BaseRepository


class BookmarkRepository(BaseRepository[Bookmark]):
    model = Bookmark

    async def get_by_user_and_post(self, user_id: uuid.UUID, post_id: uuid.UUID) -> Bookmark | None:
        result = await self.db.execute(
            select(Bookmark).where(Bookmark.user_id == user_id, Bookmark.post_id == post_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_post(self, bookmark_id: uuid.UUID) -> Bookmark | None:
        """Eager-loads Bookmark.post (+ author/category) so the response model
        can be serialized without an async lazy-load, which SQLAlchemy's async
        ORM cannot perform outside an explicit await/greenlet context."""
        from app.models.post import Post

        result = await self.db.execute(
            select(Bookmark)
            .options(
                selectinload(Bookmark.post).selectinload(Post.author),
                selectinload(Bookmark.post).selectinload(Post.category),
            )
            .where(Bookmark.id == bookmark_id)
        )
        return result.unique().scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID, offset: int, limit: int) -> Sequence[Bookmark]:
        from app.models.post import Post

        result = await self.db.execute(
            select(Bookmark)
            .options(
                selectinload(Bookmark.post).selectinload(Post.author),
                selectinload(Bookmark.post).selectinload(Post.category),
            )
            .where(Bookmark.user_id == user_id)
            .order_by(Bookmark.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.unique().scalars().all()

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        from sqlalchemy import func

        result = await self.db.execute(
            select(func.count()).select_from(Bookmark).where(Bookmark.user_id == user_id)
        )
        return result.scalar_one()


class LikeRepository(BaseRepository[PostLike]):
    model = PostLike

    async def get_by_user_and_post(self, user_id: uuid.UUID, post_id: uuid.UUID) -> PostLike | None:
        result = await self.db.execute(
            select(PostLike).where(PostLike.user_id == user_id, PostLike.post_id == post_id)
        )
        return result.scalar_one_or_none()
