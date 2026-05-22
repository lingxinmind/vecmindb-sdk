"""VecminDB SDK Authentication Manager.

Supports two authentication modes:

1. **API Key** – sent via the ``x-api-key`` header.  Keys are long-lived
   and require no refresh logic.
2. **JWT** – obtained by calling ``POST /api/v1/cluster/login`` with an
   admin password.  JWTs have a limited TTL; this module automatically
   refreshes them before expiry.

Both modes can be active simultaneously.  When a JWT is available it is
sent via the standard ``Authorization: Bearer <token>`` header.  When only
an API key is present, it is sent via ``x-api-key``.
"""

from __future__ import annotations

import time
import threading
from typing import Any, Dict, Optional

from .exceptions import AuthenticationError


class AuthManager:
    """Manages API-Key and JWT authentication for VecminDB clients.

    The manager is thread-safe – JWT refresh uses a lock so that concurrent
    requests do not initiate multiple refreshes at once.

    Args:
        api_key: Long-lived API key (admin or viewer).
        jwt_token: Pre-obtained JWT bearer token.
        jwt_expires_at: Epoch timestamp when *jwt_token* expires.
        admin_password: Password used to obtain a new JWT via the login
            endpoint.  Must be provided if automatic JWT refresh is desired.
        refresh_margin_seconds: How many seconds before expiry a proactive
            refresh is attempted.  Defaults to 60 s.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        jwt_token: Optional[str] = None,
        jwt_expires_at: Optional[float] = None,
        admin_password: Optional[str] = None,
        refresh_margin_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._jwt_token = jwt_token
        self._jwt_expires_at = jwt_expires_at or 0.0
        self._admin_password = admin_password
        self._refresh_margin = refresh_margin_seconds
        self._lock = threading.Lock()
        # Will be set by the client after construction to avoid circular imports.
        self._login_fn: Any = None  # Callable[[str], tuple[str, int]]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def api_key(self) -> Optional[str]:
        """Return the configured API key, if any."""
        return self._api_key

    @property
    def jwt_token(self) -> Optional[str]:
        """Return the current JWT token (may be ``None``)."""
        return self._jwt_token

    def set_login_fn(self, fn: Any) -> None:
        """Register the async/sync login callable used for JWT refresh.

        The callable must accept a single ``password: str`` argument and
        return ``(token: str, expires_in: int)``.
        """
        self._login_fn = fn

    def auth_headers(self) -> Dict[str, str]:
        """Build the authentication headers for an outgoing request.

        Returns:
            A dict containing the appropriate ``x-api-key`` and/or
            ``Authorization`` headers.
        """
        headers: Dict[str, str] = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        jwt = self._maybe_refresh_jwt()
        if jwt:
            headers["Authorization"] = f"Bearer {jwt}"
        return headers

    def extra_headers(self, agent_id: Optional[str] = None, model_id: Optional[str] = None, request_id: Optional[str] = None) -> Dict[str, str]:
        """Build optional tracing / identity headers.

        Args:
            agent_id: Value for the ``x-agent-id`` header.
            model_id: Value for the ``x-model-id`` header.
            request_id: Value for the ``x-request-id`` header.

        Returns:
            Dict of non-empty headers.
        """
        headers: Dict[str, str] = {}
        if agent_id:
            headers["x-agent-id"] = agent_id
        if model_id:
            headers["x-model-id"] = model_id
        if request_id:
            headers["x-request-id"] = request_id
        return headers

    # ------------------------------------------------------------------
    # JWT lifecycle
    # ------------------------------------------------------------------

    def is_jwt_expired(self) -> bool:
        """Check whether the current JWT is expired or about to expire."""
        if not self._jwt_token:
            return True
        return time.time() >= (self._jwt_expires_at - self._refresh_margin)

    def update_jwt(self, token: str, expires_in: int) -> None:
        """Replace the stored JWT with a freshly obtained one.

        Args:
            token: New JWT bearer token.
            expires_in: Token validity in seconds from now.
        """
        with self._lock:
            self._jwt_token = token
            self._jwt_expires_at = time.time() + expires_in

    def _maybe_refresh_jwt(self) -> Optional[str]:
        """Return a valid JWT, proactively refreshing when necessary.

        This method is *synchronous* and only triggers the synchronous
        refresh path.  The async client calls ``async_refresh_jwt()``
        instead.
        """
        if not self._jwt_token:
            return None
        if not self.is_jwt_expired():
            return self._jwt_token
        # Attempt synchronous refresh
        if self._admin_password and self._login_fn:
            with self._lock:
                # Double-check under lock – another thread may have refreshed.
                if not self.is_jwt_expired():
                    return self._jwt_token
                try:
                    token, expires_in = self._login_fn(self._admin_password)
                    self._jwt_token = token
                    self._jwt_expires_at = time.time() + expires_in
                except Exception as exc:
                    raise AuthenticationError(
                        f"JWT refresh failed: {exc}"
                    ) from exc
        return self._jwt_token

    async def async_maybe_refresh_jwt(self) -> Optional[str]:
        """Async variant of :meth:`_maybe_refresh_jwt`."""
        if not self._jwt_token:
            return None
        if not self.is_jwt_expired():
            return self._jwt_token
        if self._admin_password and self._login_fn:
            # Use a threading lock even in async context – the actual
            # network call is awaited, but we prevent concurrent refreshes.
            with self._lock:
                if not self.is_jwt_expired():
                    return self._jwt_token
                try:
                    result = self._login_fn(self._admin_password)
                    # Support both sync and async login callables.
                    if hasattr(result, "__await__"):
                        token, expires_in = await result  # type: ignore[misc]
                    else:
                        token, expires_in = result  # type: ignore[misc]
                    self._jwt_token = token
                    self._jwt_expires_at = time.time() + expires_in
                except Exception as exc:
                    raise AuthenticationError(
                        f"JWT refresh failed: {exc}"
                    ) from exc
        return self._jwt_token
