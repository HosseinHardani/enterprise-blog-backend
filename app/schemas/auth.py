from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import PasswordValidatorMixin


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token lifetime in seconds")


class EmailVerificationRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel, PasswordValidatorMixin):
    token: str
    password: str = Field(..., min_length=8, max_length=128)
