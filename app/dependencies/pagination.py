from fastapi import Query

from app.core.config import settings
from app.utils.pagination import PageParams


def pagination_params(
    page: int = Query(1, ge=1, description="Page number, starting at 1"),
    page_size: int = Query(
        settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE, description="Items per page"
    ),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)
