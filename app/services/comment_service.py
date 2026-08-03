import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import ForbiddenError, NotFoundError, ValidationError
from app.models.comment import Comment
from app.models.user import User, UserRole
from app.repositories.comment import CommentRepository
from app.repositories.post import PostRepository


class CommentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.comments = CommentRepository(db)
        self.posts = PostRepository(db)

    async def create(
        self,
        post_id: uuid.UUID,
        author: User,
        content: str,
        parent_id: uuid.UUID | None,
    ) -> Comment:
        post = await self.posts.get_by_id(post_id)
        if post is None:
            raise NotFoundError("Post not found")

        if parent_id is not None:
            parent = await self.comments.get_by_id(parent_id)
            if parent is None or parent.post_id != post_id:
                raise ValidationError("Parent comment does not exist on this post")

        comment = await self.comments.create(
            content=content,
            post_id=post_id,
            author_id=author.id,
            parent_id=parent_id,
        )

        await self.db.commit()

        created_comment = await self.comments.get_by_id(comment.id)

        if created_comment is None:
            raise NotFoundError("Comment not found")

        return created_comment

    async def list_for_post(
        self,
        post_id: uuid.UUID,
        offset: int,
        limit: int,
    ) -> tuple[list[Comment], int]:
        items = await self.comments.list_top_level_for_post(
            post_id,
            offset,
            limit,
        )

        total = await self.comments.count_top_level_for_post(post_id)

        return list(items), total

    async def get_by_id_or_404(
        self,
        comment_id: uuid.UUID,
    ) -> Comment:
        comment = await self.comments.get_by_id(comment_id)

        if comment is None:
            raise NotFoundError("Comment not found")

        return comment

    async def update(
        self,
        comment_id: uuid.UUID,
        actor: User,
        content: str,
    ) -> Comment:
        comment = await self.get_by_id_or_404(comment_id)

        if comment.author_id != actor.id and actor.role != UserRole.ADMIN:
            raise ForbiddenError("You do not have permission to edit this comment")

        comment.content = content

        await self.db.flush()
        await self.db.commit()

        updated_comment = await self.comments.get_by_id(comment.id)

        if updated_comment is None:
            raise NotFoundError("Comment not found")

        return updated_comment

    async def delete(
        self,
        comment_id: uuid.UUID,
        actor: User,
    ) -> None:
        comment = await self.get_by_id_or_404(comment_id)

        if comment.author_id != actor.id and actor.role not in (UserRole.ADMIN, UserRole.EDITOR):
            raise ForbiddenError("You do not have permission to delete this comment")

        comment.is_deleted = True
        comment.deleted_at = datetime.now(UTC)

        await self.db.commit()
