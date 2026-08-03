import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import require_editor_or_admin
from app.dependencies.pagination import pagination_params
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.tag import TagCreate, TagResponse
from app.services.tag_service import TagService
from app.utils.pagination import PageParams

router = APIRouter(prefix="/tags", tags=["Tags"])


@router.get("", response_model=PaginatedResponse[TagResponse], summary="List all tags")
async def list_tags(
    page_params: PageParams = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
):
    service = TagService(db)
    items, total = await service.list_all(page_params.offset, page_params.limit)
    return PaginatedResponse.create(items, total, page_params.page, page_params.page_size)


@router.post("", response_model=TagResponse, status_code=201, summary="[Editor/Admin] Create a tag")
async def create_tag(
    payload: TagCreate,
    current_user: User = Depends(require_editor_or_admin),
    db: AsyncSession = Depends(get_db),
):
    service = TagService(db)
    return await service.create(payload.name)


@router.delete("/{tag_id}", response_model=MessageResponse, summary="[Editor/Admin] Delete a tag")
async def delete_tag(
    tag_id: uuid.UUID,
    current_user: User = Depends(require_editor_or_admin),
    db: AsyncSession = Depends(get_db),
):
    service = TagService(db)
    await service.delete(tag_id)
    return MessageResponse(message="Tag deleted")
