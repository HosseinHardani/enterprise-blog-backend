import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import AlreadyExistsError, NotFoundError
from app.models.bookmark import Bookmark
from app.models.user import User
from app.repositories.bookmark import BookmarkRepository
from app.repositories.post import PostRepository


class BookmarkService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.bookmarks = BookmarkRepository(db)
        self.posts = PostRepository(db)

    async def add(self, user: User, post_id: uuid.UUID) -> Bookmark:
        post = await self.posts.get_by_id(post_id)
        if post is None:
            raise NotFoundError("Post not found")

        existing = await self.bookmarks.get_by_user_and_post(user.id, post_id)
        if existing is not None:
            raise AlreadyExistsError("Post already bookmarked")

        bookmark = await self.bookmarks.create(
            user_id=user.id,
            post_id=post_id,
        )

        await self.db.commit()

        created_bookmark = await self.bookmarks.get_by_id_with_post(bookmark.id)
        if created_bookmark is None:
            raise NotFoundError("Bookmark not found after creation")

        return created_bookmark

    async def remove(self, user: User, post_id: uuid.UUID) -> None:
        existing = await self.bookmarks.get_by_user_and_post(user.id, post_id)
        if existing is None:
            raise NotFoundError("Bookmark not found")

        await self.bookmarks.delete(existing)
        await self.db.commit()

    async def list_for_user(
        self,
        user: User,
        offset: int,
        limit: int,
    ):
        items = await self.bookmarks.list_for_user(user.id, offset, limit)
        total = await self.bookmarks.count_for_user(user.id)
        return items, total
