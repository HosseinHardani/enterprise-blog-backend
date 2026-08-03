import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import ForbiddenError, NotFoundError
from app.models.post import Post, PostStatus
from app.models.user import User, UserRole
from app.repositories.bookmark import BookmarkRepository, LikeRepository
from app.repositories.category import CategoryRepository
from app.repositories.post import PostRepository
from app.repositories.tag import TagRepository
from app.utils.slug import generate_slug, generate_unique_slug


def _can_modify(user: User, post: Post) -> bool:
    return user.role in (UserRole.ADMIN, UserRole.EDITOR) or post.author_id == user.id


class PostService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.posts = PostRepository(db)
        self.categories = CategoryRepository(db)
        self.tags = TagRepository(db)
        self.bookmarks = BookmarkRepository(db)
        self.likes = LikeRepository(db)

    async def create(
        self,
        author: User,
        title: str,
        content: str,
        excerpt: str | None,
        cover_image_url: str | None,
        category_id: uuid.UUID | None,
        tag_ids: list[uuid.UUID],
        status: PostStatus,
    ) -> Post:
        if category_id is not None and await self.categories.get_by_id(category_id) is None:
            raise NotFoundError("Category not found")

        slug = generate_slug(title)

        if await self.posts.get_by_slug(slug):
            slug = generate_unique_slug(title)

        tags = await self.tags.get_by_ids(tag_ids) if tag_ids else []

        post = Post(
            title=title,
            slug=slug,
            content=content,
            excerpt=excerpt,
            cover_image_url=cover_image_url,
            category_id=category_id,
            status=status,
            author_id=author.id,
            tags=tags,
        )

        self.db.add(post)

        await self.db.flush()

        await self.db.refresh(
            post,
            attribute_names=[
                "author",
                "category",
                "tags",
            ],
        )

        await self.db.commit()

        created_post = await self.posts.get_by_id(post.id)

        if created_post is None:
            raise NotFoundError("Post not found")

        return created_post

    async def get_by_id_or_404(
        self,
        post_id: uuid.UUID,
    ) -> Post:
        post = await self.posts.get_by_id(post_id)

        if post is None:
            raise NotFoundError("Post not found")

        return post

    async def get_by_slug_or_404(
        self,
        slug: str,
        increment_view: bool = False,
    ) -> Post:
        post = await self.posts.get_by_slug(slug)

        if post is None:
            raise NotFoundError("Post not found")

        if increment_view:
            await self.posts.increment_view_count(post)
            await self.db.commit()

        return post

    async def list_posts(
        self,
        *,
        offset: int,
        limit: int,
        status: PostStatus | None,
        category_id: uuid.UUID | None,
        tag_id: uuid.UUID | None,
        author_id: uuid.UUID | None,
        search: str | None,
        sort_by: str,
        sort_order: str,
    ):
        return await self.posts.list_filtered(
            offset=offset,
            limit=limit,
            status=status,
            category_id=category_id,
            tag_id=tag_id,
            author_id=author_id,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def update(
        self,
        post_id: uuid.UUID,
        actor: User,
        title: str | None,
        content: str | None,
        excerpt: str | None,
        cover_image_url: str | None,
        category_id: uuid.UUID | None,
        tag_ids: list[uuid.UUID] | None,
        status: PostStatus | None,
    ) -> Post:
        post = await self.get_by_id_or_404(post_id)

        if not _can_modify(actor, post):
            raise ForbiddenError("You do not have permission to modify this post")

        if category_id is not None and await self.categories.get_by_id(category_id) is None:
            raise NotFoundError("Category not found")

        if title is not None and title != post.title:
            new_slug = generate_slug(title)

            if new_slug != post.slug and await self.posts.get_by_slug(new_slug):
                new_slug = generate_unique_slug(title)

            post.title = title
            post.slug = new_slug

        if content is not None:
            post.content = content

        if excerpt is not None:
            post.excerpt = excerpt

        if cover_image_url is not None:
            post.cover_image_url = cover_image_url

        if category_id is not None:
            post.category_id = category_id

        if status is not None:
            post.status = status

        if tag_ids is not None:
            post.tags = await self.tags.get_by_ids(tag_ids)

        await self.db.flush()
        await self.db.commit()

        updated_post = await self.posts.get_by_id(post.id)

        if updated_post is None:
            raise NotFoundError("Post not found")

        return updated_post

    async def delete(
        self,
        post_id: uuid.UUID,
        actor: User,
    ) -> None:
        post = await self.get_by_id_or_404(post_id)

        if not _can_modify(actor, post):
            raise ForbiddenError("You do not have permission to delete this post")

        post.is_deleted = True
        post.deleted_at = datetime.now(UTC)

        await self.db.commit()

    async def toggle_like(
        self,
        post_id: uuid.UUID,
        user: User,
    ) -> bool:
        await self.get_by_id_or_404(post_id)

        existing = await self.likes.get_by_user_and_post(
            user.id,
            post_id,
        )

        if existing:
            await self.likes.delete(existing)
            await self.db.commit()
            return False

        await self.likes.create(
            user_id=user.id,
            post_id=post_id,
        )

        await self.db.commit()

        return True

    async def enrich_with_counts_and_status(
        self,
        post: Post,
        user: User | None,
    ) -> dict:
        like_count = await self.posts.get_like_count(post.id)
        comment_count = await self.posts.get_comment_count(post.id)

        is_liked = False
        is_bookmarked = False

        if user is not None:
            is_liked = (await self.likes.get_by_user_and_post(user.id, post.id)) is not None

            is_bookmarked = (await self.bookmarks.get_by_user_and_post(user.id, post.id)) is not None

        return {
            "like_count": like_count,
            "comment_count": comment_count,
            "is_liked": is_liked,
            "is_bookmarked": is_bookmarked,
        }
