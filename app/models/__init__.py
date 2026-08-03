"""
Import all models here so Alembic autogenerate and Base.metadata can see them.
"""

from app.database.base import Base
from app.models.bookmark import Bookmark
from app.models.category import Category
from app.models.comment import Comment
from app.models.like import PostLike
from app.models.post import Post, post_tags
from app.models.refresh_token import RefreshToken
from app.models.tag import Tag
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Post",
    "post_tags",
    "Comment",
    "Category",
    "Tag",
    "Bookmark",
    "PostLike",
    "RefreshToken",
]
