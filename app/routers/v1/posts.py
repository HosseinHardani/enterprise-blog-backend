import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import get_current_user, get_optional_current_user
from app.dependencies.pagination import pagination_params
from app.models.post import PostStatus
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.post import PostCreate, PostDetail, PostListItem, PostUpdate
from app.services.post_service import PostService
from app.utils.pagination import PageParams

router = APIRouter(prefix="/posts", tags=["Posts"])


async def _to_list_item(post, service: PostService, user: User | None) -> PostListItem:
    counts = await service.enrich_with_counts_and_status(post, user)
    item = PostListItem.model_validate(post)
    return item.model_copy(update={"like_count": counts["like_count"], "comment_count": counts["comment_count"]})


async def _to_detail(post, service: PostService, user: User | None) -> PostDetail:
    counts = await service.enrich_with_counts_and_status(post, user)
    detail = PostDetail.model_validate(post)
    return detail.model_copy(update=counts)


@router.get("", response_model=PaginatedResponse[PostListItem], summary="List posts with filtering, search, sorting")
async def list_posts(
    page_params: PageParams = Depends(pagination_params),
    status_filter: PostStatus | None = Query(None, alias="status"),
    category_id: uuid.UUID | None = Query(None),
    tag_id: uuid.UUID | None = Query(None),
    author_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None, min_length=1, max_length=200),
    sort_by: str = Query("created_at", pattern="^(created_at|title|view_count)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PostService(db)
    is_privileged = current_user is not None and current_user.role.value in ("admin", "editor")
    effective_status = status_filter
    if not is_privileged and status_filter != PostStatus.PUBLISHED:
        effective_status = PostStatus.PUBLISHED

    posts, total = await service.list_posts(
        offset=page_params.offset,
        limit=page_params.limit,
        status=effective_status,
        category_id=category_id,
        tag_id=tag_id,
        author_id=author_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    items = [await _to_list_item(post, service, current_user) for post in posts]
    return PaginatedResponse.create(items, total, page_params.page, page_params.page_size)


@router.get("/{slug}", response_model=PostDetail, summary="Get a post by slug (increments view count)")
async def get_post(
    slug: str,
    current_user: User | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PostService(db)
    post = await service.get_by_slug_or_404(slug, increment_view=True)
    return await _to_detail(post, service, current_user)


@router.post("", response_model=PostDetail, status_code=201, summary="Create a new post")
async def create_post(
    payload: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PostService(db)
    post = await service.create(
        author=current_user,
        title=payload.title,
        content=payload.content,
        excerpt=payload.excerpt,
        cover_image_url=payload.cover_image_url,
        category_id=payload.category_id,
        tag_ids=payload.tag_ids,
        status=payload.status,
    )
    return await _to_detail(post, service, current_user)


@router.patch("/{post_id}", response_model=PostDetail, summary="Update a post (author, editor, or admin)")
async def update_post(
    post_id: uuid.UUID,
    payload: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PostService(db)
    post = await service.update(
        post_id=post_id,
        actor=current_user,
        title=payload.title,
        content=payload.content,
        excerpt=payload.excerpt,
        cover_image_url=payload.cover_image_url,
        category_id=payload.category_id,
        tag_ids=payload.tag_ids,
        status=payload.status,
    )
    return await _to_detail(post, service, current_user)


@router.delete("/{post_id}", response_model=MessageResponse, summary="Delete a post (author, editor, or admin)")
async def delete_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PostService(db)
    await service.delete(post_id, current_user)
    return MessageResponse(message="Post deleted")


@router.post("/{post_id}/like", response_model=MessageResponse, summary="Toggle a like on a post")
async def toggle_like(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PostService(db)
    now_liked = await service.toggle_like(post_id, current_user)
    return MessageResponse(message="Post liked" if now_liked else "Like removed")
