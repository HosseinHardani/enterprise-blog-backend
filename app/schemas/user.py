import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]+$")


class PasswordValidatorMixin:
    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain at least one digit")
        return value


class UserRegister(BaseModel, PasswordValidatorMixin):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=150)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not USERNAME_PATTERN.match(value):
            raise ValueError("Username may only contain letters, numbers, and underscores")
        return value


class UserPublic(BaseModel):
    """Public-facing user data - safe to expose to anyone."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    full_name: str | None
    bio: str | None
    profile_image_url: str | None
    created_at: datetime


class UserMe(UserPublic):
    """Full profile data - only for the authenticated user themselves."""

    email: EmailStr
    role: UserRole
    is_active: bool
    is_email_verified: bool
    updated_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, max_length=150)
    bio: str | None = Field(None, max_length=500)


class UserChangeEmail(BaseModel):
    new_email: EmailStr
    current_password: str


class UserChangePassword(BaseModel, PasswordValidatorMixin):
    current_password: str
    password: str = Field(..., min_length=8, max_length=128, alias="new_password")

    model_config = ConfigDict(populate_by_name=True)


class UserRoleUpdate(BaseModel):
    role: UserRole
