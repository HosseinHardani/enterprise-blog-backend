import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.post import PostStatus
from app.schemas.category import CategoryResponse
from app.schemas.tag import TagResponse
from app.schemas.user import UserPublic


class PostCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    content: str = Field(..., min_length=1)
    excerpt: str | None = Field(None, max_length=500)
    cover_image_url: str | None = Field(None, max_length=500)
    category_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] = Field(default_factory=list)
    status: PostStatus = PostStatus.DRAFT


class PostUpdate(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=255)
    content: str | None = Field(None, min_length=1)
    excerpt: str | None = Field(None, max_length=500)
    cover_image_url: str | None = Field(None, max_length=500)
    category_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] | None = None
    status: PostStatus | None = None


class PostListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    excerpt: str | None
    cover_image_url: str | None
    status: PostStatus
    view_count: int
    author: UserPublic
    category: CategoryResponse | None
    created_at: datetime
    like_count: int = 0
    comment_count: int = 0


class PostDetail(PostListItem):
    content: str
    tags: list[TagResponse] = Field(default_factory=list)
    updated_at: datetime
    is_bookmarked: bool = False
    is_liked: bool = False
