from fastapi import APIRouter

from app.routers.v1 import auth, bookmarks, categories, comments, posts, tags, users

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(posts.router)
api_router.include_router(comments.router)
api_router.include_router(categories.router)
api_router.include_router(tags.router)
api_router.include_router(bookmarks.router)
