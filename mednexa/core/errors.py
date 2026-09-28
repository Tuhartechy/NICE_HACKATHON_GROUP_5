"""
Standard error model for MedNexa services.

Services raise these exceptions; pages catch ServiceError and show only
`user_message` - never a stack trace. This replaces the original Feature 2
HTTP error envelope {"error": {"code", "message"}} (see ServiceError.to_dict).
"""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for every expected, user-presentable failure."""

    default_code = "SERVICE_ERROR"
    default_message = "Something went wrong. Please try again."

    def __init__(self, message: str | None = None, *, code: str | None = None,
                 details: dict | None = None):
        self.code = code or self.default_code
        self.user_message = message or self.default_message
        self.details = dict(details or {})
        super().__init__(self.user_message)

    def to_dict(self) -> dict:
        body = {"code": self.code, "message": self.user_message}
        if self.details:
            body["details"] = self.details
        return {"error": body}


class ValidationError(ServiceError):
    """Input failed validation. `field_errors` maps field name -> message."""

    default_code = "VALIDATION_ERROR"
    default_message = "Please correct the highlighted fields."

    def __init__(self, message: str | None = None, *, field_errors: dict | None = None,
                 code: str | None = None):
        self.field_errors = dict(field_errors or {})
        super().__init__(message, code=code, details={"fields": self.field_errors} if field_errors else None)


class NotFoundError(ServiceError):
    default_code = "NOT_FOUND"
    default_message = "The requested record could not be found."


class PermissionDeniedError(ServiceError):
    default_code = "PERMISSION_DENIED"
    default_message = "Your current role does not allow this action."


class ConflictError(ServiceError):
    """The operation conflicts with current data (duplicate, insufficient stock, stale state)."""

    default_code = "CONFLICT"
    default_message = "This change conflicts with the current data."


class DataUnavailableError(ServiceError):
    """The application database has not been initialised or cannot be read."""

    default_code = "DATA_UNAVAILABLE"
    default_message = ("The MedNexa database is not available yet. "
                       "Run `python -m mednexa.db.seed` and reload the app.")
