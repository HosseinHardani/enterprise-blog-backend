import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.pagination import pagination_params
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentResponse, CommentUpdate
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.comment_service import CommentService
from app.utils.pagination import PageParams

router = APIRouter(tags=["Comments"])


@router.get(
    "/posts/{post_id}/comments",
    response_model=PaginatedResponse[CommentResponse],
    summary="List top-level comments for a post (with nested replies)",
)
async def list_comments(
    post_id: uuid.UUID,
    page_params: PageParams = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
):
    service = CommentService(db)
    items, total = await service.list_for_post(post_id, page_params.offset, page_params.limit)
    return PaginatedResponse.create(items, total, page_params.page, page_params.page_size)


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=201,
    summary="Add a comment (or reply) to a post",
)
async def create_comment(
    post_id: uuid.UUID,
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CommentService(db)
    return await service.create(post_id, current_user, payload.content, payload.parent_id)


@router.patch(
    "/comments/{comment_id}", response_model=CommentResponse, summary="Edit a comment (author or admin)"
)
async def update_comment(
    comment_id: uuid.UUID,
    payload: CommentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CommentService(db)
    return await service.update(comment_id, current_user, payload.content)


@router.delete(
    "/comments/{comment_id}",
    response_model=MessageResponse,
    summary="Delete a comment (author, editor, or admin)",
)
async def delete_comment(
    comment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CommentService(db)
    await service.delete(comment_id, current_user)
    return MessageResponse(message="Comment deleted")
