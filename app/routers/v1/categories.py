import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies.auth import require_editor_or_admin
from app.dependencies.pagination import pagination_params
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.category_service import CategoryService
from app.utils.pagination import PageParams

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=PaginatedResponse[CategoryResponse], summary="List all categories")
async def list_categories(
    page_params: PageParams = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
):
    service = CategoryService(db)
    items, total = await service.list_all(page_params.offset, page_params.limit)
    return PaginatedResponse.create(items, total, page_params.page, page_params.page_size)


@router.get("/{category_id}", response_model=CategoryResponse, summary="Get a category by ID")
async def get_category(category_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = CategoryService(db)
    return await service.get_by_id_or_404(category_id)


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=201,
    summary="[Editor/Admin] Create a category",
)
async def create_category(
    payload: CategoryCreate,
    current_user: User = Depends(require_editor_or_admin),
    db: AsyncSession = Depends(get_db),
):
    service = CategoryService(db)
    return await service.create(payload.name, payload.description)


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="[Editor/Admin] Update a category",
)
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    current_user: User = Depends(require_editor_or_admin),
    db: AsyncSession = Depends(get_db),
):
    service = CategoryService(db)
    return await service.update(category_id, payload.name, payload.description)


@router.delete(
    "/{category_id}",
    response_model=MessageResponse,
    summary="[Editor/Admin] Delete a category",
)
async def delete_category(
    category_id: uuid.UUID,
    current_user: User = Depends(require_editor_or_admin),
    db: AsyncSession = Depends(get_db),
):
    service = CategoryService(db)
    await service.delete(category_id)
    return MessageResponse(message="Category deleted")
