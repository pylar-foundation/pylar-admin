"""Authentication endpoints for the admin panel.

These routes run WITHOUT RequireAuthMiddleware so unauthenticated
users can reach the login form.

    POST /admin/api/login                       → email + password
    POST /admin/api/logout                      → destroy session
    GET  /admin/api/user                        → current user info (or 401)
    GET  /admin/api/login/webauthn/options      → passkey challenge
    POST /admin/api/login/webauthn/verify       → assertion → session
"""

from __future__ import annotations

import logging
from typing import Any

from pylar.auth.config import AuthConfig
from pylar.auth.contracts import Authenticatable, Guard
from pylar.auth.hashing import PasswordHasher
from pylar.database.session import current_session
from pylar.foundation.container import Container
from pylar.http import JsonResponse, Request, Response

_logger = logging.getLogger("pylar.admin.auth")


class AdminAuthController:
    """Handles login, logout, and current-user queries for the admin SPA.

    All required dependencies (Guard, PasswordHasher, AuthConfig) are
    injected by the container via the constructor. ``container`` is
    kept as an optional reference so the WebAuthn login path can
    resolve a :class:`WebauthnServer` lazily — that service is only
    bound when the app installs ``pylar[webauthn]`` and adds the
    matching provider, so direct injection would reject every
    project that skips the extras.
    """

    def __init__(
        self,
        guard: Guard,
        hasher: PasswordHasher,
        config: AuthConfig,
        container: Container,
    ) -> None:
        self._guard = guard
        self._hasher = hasher
        self._user_cls = self._resolve_user_model(config)
        self._container = container

    async def login(self, request: Request) -> Response:
        """Authenticate with email and password, create a session."""
        from pylar.auth.session_guard import SessionGuard

        # Brute-force protection: reject early if locked out.
        if isinstance(self._guard, SessionGuard) and self._guard.is_locked_out():
            return JsonResponse(
                {"message": "Too many login attempts. Try again later.", "code": 429},
                status_code=429,
            )

        body = await request.json()
        email = body.get("email", "").strip()
        password = body.get("password", "")

        if not email or not password:
            return JsonResponse(
                {"message": "Email and password are required", "code": 422},
                status_code=422,
            )

        if self._user_cls is None:
            return JsonResponse(
                {"message": "Auth not configured", "code": 500},
                status_code=500,
            )

        # Query user by email.
        session = current_session()
        user: Authenticatable | None = None
        try:
            user = await self._user_cls.query.where(
                self._user_cls.email == email
            ).first(session=session)
        except Exception:
            _logger.exception("Failed to query user by email during login")

        if user is None:
            _logger.warning("Login failed: no user found for email=%s", email)
            if isinstance(self._guard, SessionGuard):
                self._guard.record_failed_attempt()
            return JsonResponse(
                {"message": "Invalid credentials", "code": 401},
                status_code=401,
            )

        # Verify password.
        if not self._hasher.verify(password, user.auth_password_hash):
            _logger.warning(
                "Login failed: password mismatch for user_id=%s",
                user.auth_identifier,
            )
            if isinstance(self._guard, SessionGuard):
                self._guard.record_failed_attempt()
            return JsonResponse(
                {"message": "Invalid credentials", "code": 401},
                status_code=401,
            )

        # Login — write user ID to session (also clears attempt counter).
        if isinstance(self._guard, SessionGuard):
            await self._guard.login(user)

        return JsonResponse({
            "message": "Authenticated",
            "user": _serialize_user(user),
        })

    async def logout(self, request: Request) -> Response:
        """Destroy the current session."""
        from pylar.auth.session_guard import SessionGuard

        if isinstance(self._guard, SessionGuard):
            await self._guard.logout()

        return JsonResponse({"message": "Logged out"})

    async def user(self, request: Request) -> Response:
        """Return the currently authenticated user, or 401."""
        from pylar.auth.context import current_user_or_none

        user = current_user_or_none()
        if user is None:
            return JsonResponse(
                {"message": "Unauthenticated", "code": 401},
                status_code=401,
            )
        return JsonResponse({"user": _serialize_user(user)})

    # ------------------------------------------------ WebAuthn login

    async def webauthn_options(self, request: Request) -> Response:
        """Generate a passkey assertion challenge for the login page.

        Uses the discoverable-credential flow (``user=None``) so the
        browser offers every resident credential scoped to this RP —
        the user doesn't have to type their email first. Returns the
        WebAuthn options JSON the SPA hands to
        ``navigator.credentials.get()``.
        """
        server = self._webauthn_server()
        if server is None:
            return JsonResponse(
                {"message": "WebAuthn is not configured for this deployment",
                 "code": 404},
                status_code=404,
            )
        options = await server.make_authentication_options()
        return JsonResponse(options)

    async def webauthn_verify(self, request: Request) -> Response:
        """Verify a passkey assertion and log the user in.

        Expects the browser's ``PublicKeyCredential`` response as JSON
        body. On success pins the authenticated user to the session
        via :class:`SessionGuard` — same login flow the password path
        uses — so downstream requests see ``current_user()``.
        """
        from pylar.auth.session_guard import SessionGuard
        from pylar.auth.webauthn import WebauthnError

        server = self._webauthn_server()
        if server is None:
            return JsonResponse(
                {"message": "WebAuthn is not configured for this deployment",
                 "code": 404},
                status_code=404,
            )

        body = await request.json()
        if not isinstance(body, dict):
            return JsonResponse(
                {"message": "Assertion payload must be a JSON object",
                 "code": 422},
                status_code=422,
            )

        try:
            user, _credential = await server.verify_authentication(
                body, origin=_request_origin(request),
            )
        except WebauthnError as exc:
            _logger.warning("WebAuthn login rejected: %s", exc)
            # Don't leak whether the credential existed or the
            # signature was invalid — collapses to the same 401 the
            # password path uses.
            return JsonResponse(
                {"message": "Invalid passkey", "code": 401},
                status_code=401,
            )

        if isinstance(self._guard, SessionGuard):
            await self._guard.login(user)

        return JsonResponse({
            "message": "Authenticated",
            "user": _serialize_user(user),
        })

    def _webauthn_server(self) -> Any | None:
        """Resolve the optional :class:`WebauthnServer` singleton.

        Returns ``None`` when the feature is not configured — the
        calling endpoints collapse that into a 404 so the SPA can
        hide the "Sign in with passkey" button without surfacing a
        scary error.
        """
        try:
            from pylar.auth.webauthn import WebauthnServer
        except ImportError:
            return None
        if not self._container.has(WebauthnServer):
            return None
        return self._container.make(WebauthnServer)

    @staticmethod
    def _resolve_user_model(config: AuthConfig) -> type[Any] | None:
        """Resolve the user model class from the config string once."""
        from pylar.auth.provider import _resolve_class

        return _resolve_class(config.user_model)


def _serialize_user(user: Authenticatable) -> dict[str, Any]:
    """Serialize a user for JSON response."""
    data: dict[str, Any] = {"id": user.auth_identifier}
    for attr in ("name", "email", "is_admin"):
        val = getattr(user, attr, None)
        if val is not None:
            data[attr] = val
    return data


def _request_origin(request: Request) -> str | None:
    """Return the browser-reported origin for *request*.

    Prefers the ``Origin`` header — it's what browsers populate on
    fetch/XHR and matches exactly what ends up in WebAuthn's
    clientDataJSON. Falls back to scheme + host from the URL so
    non-browser clients still work in tests.
    """
    header = request.headers.get("origin")
    if header:
        return header
    url = request.url
    if not url.hostname:
        return None
    if url.port and url.port not in (80, 443):
        return f"{url.scheme}://{url.hostname}:{url.port}"
    return f"{url.scheme}://{url.hostname}"
