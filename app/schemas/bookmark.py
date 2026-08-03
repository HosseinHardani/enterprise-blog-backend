import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.post import PostListItem


class BookmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    post: PostListItem
    created_at: datetime
