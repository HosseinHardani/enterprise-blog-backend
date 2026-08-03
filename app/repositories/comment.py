import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.repositories.base import BaseRepository


def _comment_load_options():
    return [
        selectinload(Comment.author),
        selectinload(Comment.replies).selectinload(Comment.author),
        selectinload(Comment.replies).selectinload(Comment.replies).selectinload(Comment.author),
    ]


class CommentRepository(BaseRepository[Comment]):
    model = Comment

    async def get_by_id(self, id_: uuid.UUID) -> Comment | None:
        result = await self.db.execute(
            select(Comment)
            .options(*_comment_load_options())
            .where(
                Comment.id == id_,
                Comment.is_deleted.is_(False),
            )
        )
        return result.unique().scalar_one_or_none()

    async def list_top_level_for_post(
        self,
        post_id: uuid.UUID,
        offset: int,
        limit: int,
    ) -> Sequence[Comment]:
        result = await self.db.execute(
            select(Comment)
            .options(*_comment_load_options())
            .where(
                Comment.post_id == post_id,
                Comment.parent_id.is_(None),
                Comment.is_deleted.is_(False),
            )
            .order_by(Comment.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        return result.unique().scalars().all()

    async def count_top_level_for_post(
        self,
        post_id: uuid.UUID,
    ) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Comment)
            .where(
                Comment.post_id == post_id,
                Comment.parent_id.is_(None),
                Comment.is_deleted.is_(False),
            )
        )

        return result.scalar_one()
