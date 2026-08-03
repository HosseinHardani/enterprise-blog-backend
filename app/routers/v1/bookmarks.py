import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.pagination import pagination_params
from app.models.user import User
from app.schemas.bookmark import BookmarkResponse
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.bookmark_service import BookmarkService
from app.utils.pagination import PageParams

router = APIRouter(prefix="/bookmarks", tags=["Bookmarks"])


@router.get(
    "", response_model=PaginatedResponse[BookmarkResponse], summary="List the current user's bookmarks"
)
async def list_bookmarks(
    page_params: PageParams = Depends(pagination_params),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BookmarkService(db)
    items, total = await service.list_for_user(current_user, page_params.offset, page_params.limit)
    return PaginatedResponse.create(items, total, page_params.page, page_params.page_size)


@router.post("/{post_id}", response_model=BookmarkResponse, status_code=201, summary="Bookmark a post")
async def add_bookmark(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BookmarkService(db)
    return await service.add(current_user, post_id)


@router.delete("/{post_id}", response_model=MessageResponse, summary="Remove a bookmark")
async def remove_bookmark(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BookmarkService(db)
    await service.remove(current_user, post_id)
    return MessageResponse(message="Bookmark removed")
