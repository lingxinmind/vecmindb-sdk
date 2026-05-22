"""VecminDB SDK Exception Hierarchy.

All SDK-specific exceptions inherit from :class:`VecminError`, making it easy
to catch any SDK-level error with a single ``except VecminError`` clause while
still allowing fine-grained handling of specific error categories.
"""

from __future__ import annotations

from typing import Optional


class VecminError(Exception):
    """Base exception for all VecminDB SDK errors.

    Attributes:
        message: Human-readable error description.
        code: Optional numeric error code returned by the server.
    """

    def __init__(self, message: str = "", code: Optional[int] = None) -> None:
        self.message = message
        self.code = code
        super().__init__(message)

    def __str__(self) -> str:  # noqa: D105
        if self.code is not None:
            return f"[{self.code}] {self.message}"
        return self.message


# ---------------------------------------------------------------------------
# Authentication & Authorization
# ---------------------------------------------------------------------------

class AuthenticationError(VecminError):
    """Raised when the server rejects credentials (HTTP 401).

    Typical causes: missing API key, expired JWT, or invalid token.
    """


class PermissionError(VecminError):
    """Raised when the authenticated principal lacks access (HTTP 403).

    For example, using a viewer-key to call a write endpoint.
    """


# ---------------------------------------------------------------------------
# Client-side errors
# ---------------------------------------------------------------------------

class NotFoundError(VecminError):
    """Raised when the requested resource does not exist (HTTP 404)."""


class BadRequestError(VecminError):
    """Raised when the request payload is malformed (HTTP 400)."""


class ConflictError(VecminError):
    """Raised on duplicate resource creation (HTTP 409)."""


class ValidationError(VecminError):
    """Raised when request data fails client-side or server-side validation (HTTP 422)."""


class RateLimitError(VecminError):
    """Raised when the server rate-limits the request (HTTP 429).

    The SDK's retry layer may handle this automatically depending on
    configuration.
    """


# ---------------------------------------------------------------------------
# Server-side errors
# ---------------------------------------------------------------------------

class ServerError(VecminError):
    """Raised on unexpected server failures (HTTP 5xx)."""


# ---------------------------------------------------------------------------
# Transport / network errors
# ---------------------------------------------------------------------------

class ConnectionError(VecminError):  # noqa: A001 – intentional shadow of builtin
    """Raised when the SDK cannot establish a TCP connection to the server."""


class TimeoutError(VecminError):  # noqa: A001 – intentional shadow of builtin
    """Raised when a request exceeds the configured timeout."""


# ---------------------------------------------------------------------------
# Mapping helper
# ---------------------------------------------------------------------------

_STATUS_CODE_TO_EXCEPTION = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
}


def exception_from_status(status_code: int, message: str = "", code: Optional[int] = None) -> VecminError:
    """Create the appropriate exception from an HTTP status code.

    Args:
        status_code: HTTP status code returned by the server.
        message: Human-readable error description.
        code: Optional numeric error code from the response body.

    Returns:
        A subclass of :class:`VecminError` matching the status code.
    """
    if 500 <= status_code < 600:
        return ServerError(message=message, code=code or status_code)
    exc_cls = _STATUS_CODE_TO_EXCEPTION.get(status_code, VecminError)
    return exc_cls(message=message, code=code or status_code)
