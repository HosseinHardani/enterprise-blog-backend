import uuid
from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.models.like import PostLike
from app.models.post import Post, PostStatus, post_tags
from app.repositories.base import BaseRepository


class PostRepository(BaseRepository[Post]):
    model = Post

    def _base_query(self):
        return select(Post).options(
            selectinload(Post.author),
            selectinload(Post.category),
            selectinload(Post.tags),
        )

    async def get_by_id(self, id_: uuid.UUID) -> Post | None:
        result = await self.db.execute(self._base_query().where(Post.id == id_, Post.is_deleted.is_(False)))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Post | None:
        result = await self.db.execute(
            self._base_query().where(Post.slug == slug, Post.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()

    async def list_filtered(
        self,
        *,
        offset: int,
        limit: int,
        status: PostStatus | None = None,
        category_id: uuid.UUID | None = None,
        tag_id: uuid.UUID | None = None,
        author_id: uuid.UUID | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[Sequence[Post], int]:
        query = self._base_query().where(Post.is_deleted.is_(False))
        count_query = (
            select(func.count(func.distinct(Post.id))).select_from(Post).where(Post.is_deleted.is_(False))
        )

        if status is not None:
            query = query.where(Post.status == status)
            count_query = count_query.where(Post.status == status)
        if category_id is not None:
            query = query.where(Post.category_id == category_id)
            count_query = count_query.where(Post.category_id == category_id)
        if author_id is not None:
            query = query.where(Post.author_id == author_id)
            count_query = count_query.where(Post.author_id == author_id)
        if tag_id is not None:
            query = query.join(post_tags, post_tags.c.post_id == Post.id).where(post_tags.c.tag_id == tag_id)
            count_query = count_query.join(post_tags, post_tags.c.post_id == Post.id).where(
                post_tags.c.tag_id == tag_id
            )
        if search:
            like = f"%{search}%"
            search_filter = or_(Post.title.ilike(like), Post.content.ilike(like), Post.excerpt.ilike(like))
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        sort_column = {
            "created_at": Post.created_at,
            "title": Post.title,
            "view_count": Post.view_count,
        }.get(sort_by, Post.created_at)
        query = query.order_by(sort_column.desc() if sort_order == "desc" else sort_column.asc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        total_result = await self.db.execute(count_query)
        return result.unique().scalars().all(), total_result.scalar_one()

    async def increment_view_count(self, post: Post) -> None:
        post.view_count += 1
        await self.db.flush()
        await self.db.refresh(post)

    async def get_like_count(self, post_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(PostLike).where(PostLike.post_id == post_id)
        )
        return result.scalar_one()

    async def get_comment_count(self, post_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Comment)
            .where(Comment.post_id == post_id, Comment.is_deleted.is_(False))
        )
        return result.scalar_one()
