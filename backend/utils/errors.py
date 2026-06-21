"""Unified exception hierarchy for TuxTackleBox."""


class AppError(Exception):
    """Base application error with HTTP status code.

    Subclasses set a default ``code`` and ``status`` suitable for their domain.
    Route handlers should never need to build raw error dicts — let the
    ``safe_api`` decorator convert these to structured JSON responses.
    """

    code: str = "INTERNAL_ERROR"
    status: int = 500

    def __init__(self, message: str = "", code: str = "", status: int = 0):
        super().__init__(message)
        self.message = message or self.__class__.__doc__ or ""
        if code:
            self.code = code
        if status:
            self.status = status

    def to_dict(self) -> dict:
        return {"success": False, "code": self.code, "message": self.message}


class AuthError(AppError):
    """Authentication required."""
    code = "AUTH_REQUIRED"
    status = 401


class ValidationError(AppError):
    """Invalid request data."""
    code = "VALIDATION_ERROR"
    status = 400


class CommandError(AppError):
    """Shell command execution failed."""
    code = "COMMAND_ERROR"
    status = 500


class NotFoundError(AppError):
    """Resource not found."""
    code = "NOT_FOUND"
    status = 404


class ConflictError(AppError):
    """Resource already exists or operation conflicts."""
    code = "CONFLICT"
    status = 409


class RateLimitError(AppError):
    """Too many requests."""
    code = "RATE_LIMITED"
    status = 429
