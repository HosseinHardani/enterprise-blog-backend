"""
Custom exception hierarchy for the application. Business/service-layer code
raises these; app.exceptions.handlers converts them into consistent JSON
responses.
"""


class AppException(Exception):
    """Base class for all custom application exceptions."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str | None = None):
        self.message = message or self.__class__.__doc__ or "An error occurred"
        super().__init__(self.message)


class NotFoundError(AppException):
    """The requested resource was not found."""

    status_code = 404
    error_code = "not_found"


class AlreadyExistsError(AppException):
    """A resource with these attributes already exists."""

    status_code = 409
    error_code = "already_exists"


class InvalidCredentialsError(AppException):
    """The provided credentials are invalid."""

    status_code = 401
    error_code = "invalid_credentials"


class UnauthorizedError(AppException):
    """Authentication is required to access this resource."""

    status_code = 401
    error_code = "unauthorized"


class ForbiddenError(AppException):
    """You do not have permission to perform this action."""

    status_code = 403
    error_code = "forbidden"


class ValidationError(AppException):
    """The provided data failed validation."""

    status_code = 422
    error_code = "validation_error"


class TokenError(AppException):
    """The provided token is invalid, expired, or revoked."""

    status_code = 401
    error_code = "invalid_token"


class RateLimitExceededError(AppException):
    """Too many requests. Please try again later."""

    status_code = 429
    error_code = "rate_limit_exceeded"


class AccountNotVerifiedError(AppException):
    """This account's email address has not been verified yet."""

    status_code = 403
    error_code = "account_not_verified"


class AccountInactiveError(AppException):
    """This account has been deactivated."""

    status_code = 403
    error_code = "account_inactive"
