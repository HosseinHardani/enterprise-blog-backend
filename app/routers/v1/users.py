import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.exceptions.custom import ValidationError
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.user import (
    UserChangeEmail,
    UserChangePassword,
    UserMe,
    UserPublic,
    UserRoleUpdate,
    UserUpdate,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.get("/{username}", response_model=UserPublic, summary="Get a user's public profile by username")
async def get_user_by_username(username: str, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    return await service.get_by_username_or_404(username)


@router.patch("/me", response_model=UserMe, summary="Update the current user's profile")
async def update_my_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    return await service.update_profile(current_user, payload.full_name, payload.bio)


@router.post(
    "/me/profile-image",
    response_model=UserMe,
    summary="Upload a profile image",
    description=f"Accepts JPEG, PNG, or WebP images up to {settings.MAX_UPLOAD_SIZE_MB}MB.",
)
async def upload_profile_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError("Only JPEG, PNG, and WebP images are allowed")

    contents = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise ValidationError(f"Image must be smaller than {settings.MAX_UPLOAD_SIZE_MB}MB")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    extension = Path(file.filename or "").suffix or ".jpg"
    filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}{extension}"
    file_path = upload_dir / filename
    file_path.write_bytes(contents)

    service = UserService(db)
    return await service.update_profile_image(current_user, image_url=f"/{upload_dir}/{filename}")


@router.post("/me/change-email", response_model=UserMe, summary="Change the current user's email address")
async def change_email(
    payload: UserChangeEmail,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    return await service.change_email(current_user, payload.new_email, payload.current_password)


@router.post(
    "/me/change-password", response_model=MessageResponse, summary="Change the current user's password"
)
async def change_password(
    payload: UserChangePassword,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.auth_service import AuthService

    service = AuthService(db)
    await service.change_password(current_user, payload.current_password, payload.password)
    return MessageResponse(message="Password changed successfully. Please log in again.")


@router.delete(
    "/me",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Soft-delete the current user's account",
)
async def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    await service.soft_delete_account(current_user)
    return MessageResponse(message="Account deleted")


@router.patch(
    "/{user_id}/role",
    response_model=UserMe,
    summary="[Admin] Change a user's role",
)
async def update_user_role(
    user_id: uuid.UUID,
    payload: UserRoleUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    return await service.update_role(current_user, user_id, payload.role)
