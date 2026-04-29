"""Self-service profile endpoints for the admin SPA.

Lets the currently authenticated user see their own details and
manage their WebAuthn credentials (register, rename, revoke). All
endpoints hard-check ``current_user()`` — nothing here is an admin
surface, so users can only touch their own rows.

The admin-wide view of every registered credential lives at
``/admin/api/system/webauthn`` (``WebauthnController``). Keep the
two distinct: one is a privileged management surface, this one is
the user's self-service page.

Endpoints (all behind ``RequireAuthMiddleware``):

* ``GET    /admin/api/profile``                           — user + own passkeys
* ``GET    /admin/api/profile/webauthn/register/options`` — start registration
* ``POST   /admin/api/profile/webauthn/register/verify``  — finish registration
* ``PATCH  /admin/api/profile/webauthn/{id}``             — rename own passkey
* ``DELETE /admin/api/profile/webauthn/{id}``             — revoke own passkey
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from pylar.auth.context import current_user_or_none
from pylar.auth.contracts import Authenticatable
from pylar.foundation.container import Container
from pylar.http import JsonResponse, Request, Response

_logger = logging.getLogger("pylar.admin.profile")


class ProfileController:
    """Self-service profile + passkey management.

    WebAuthn is optional at the framework level, so the controller
    resolves :class:`WebauthnServer` lazily through the container.
    If the module isn't bound, the passkey endpoints degrade to 404
    while the plain profile view keeps rendering.
    """

    def __init__(self, container: Container) -> None:
        self._container = container

    # --------------------------------------------------------- profile

    async def index(self, request: Request) -> Response:
        """Return the current user's profile + registered passkeys."""
        user = current_user_or_none()
        if user is None:
            return _unauthorized()

        credentials = await _load_user_credentials(user)
        return JsonResponse({
            "user": _serialize_user(user),
            "webauthn_available": self._webauthn_server() is not None,
            "credentials": [_serialize_credential(c) for c in credentials],
        })

    # ----------------------------------------------- webauthn register

    async def register_options(self, request: Request) -> Response:
        """Start a registration ceremony scoped to the current user."""
        user = current_user_or_none()
        if user is None:
            return _unauthorized()
        server = self._webauthn_server()
        if server is None:
            return _webauthn_unavailable()
        options = await server.make_registration_options(user)
        return JsonResponse(options)

    async def register_verify(self, request: Request) -> Response:
        """Finish registration and persist the credential against the current user."""
        from pylar.auth.webauthn import WebauthnError

        user = current_user_or_none()
        if user is None:
            return _unauthorized()
        server = self._webauthn_server()
        if server is None:
            return _webauthn_unavailable()

        body = await _read_json(request)
        credential_payload = body.get("credential") if isinstance(body, dict) else None
        nickname_raw = body.get("nickname") if isinstance(body, dict) else None

        if not isinstance(credential_payload, dict):
            return JsonResponse(
                {"message": "Missing 'credential' in request body", "code": 422},
                status_code=422,
            )
        nickname = (
            nickname_raw.strip()
            if isinstance(nickname_raw, str) and nickname_raw.strip()
            else None
        )

        try:
            credential = await server.verify_registration(
                user,
                credential_payload,
                nickname=nickname,
                origin=_request_origin(request),
            )
        except WebauthnError as exc:
            _logger.warning("Passkey registration rejected: %s", exc)
            return JsonResponse(
                {"message": str(exc), "code": 400},
                status_code=400,
            )

        return JsonResponse(
            {"credential": _serialize_credential(credential)},
            status_code=201,
        )

    # -------------------------------------- webauthn rename / revoke

    async def rename(self, request: Request, id: str) -> Response:
        """Rename a passkey the current user owns."""
        user = current_user_or_none()
        if user is None:
            return _unauthorized()
        model = _maybe_credential_model()
        if model is None:
            return _webauthn_unavailable()

        pk = _parse_pk(id)
        if pk is None:
            return JsonResponse(
                {"message": "credential id must be an integer", "code": 422},
                status_code=422,
            )

        credential = await _load_own_credential(model, user, pk)
        if credential is None:
            return JsonResponse(
                {"message": "Passkey not found", "code": 404},
                status_code=404,
            )

        body = await _read_json(request)
        nickname_raw = body.get("nickname") if isinstance(body, dict) else None
        if nickname_raw is not None and not isinstance(nickname_raw, str):
            return JsonResponse(
                {"message": "nickname must be a string or null", "code": 422},
                status_code=422,
            )
        from pylar.database import transaction

        credential.nickname = (
            nickname_raw.strip() if isinstance(nickname_raw, str) and nickname_raw.strip() else None
        )
        async with transaction():
            await model.query.save(credential)
        return JsonResponse({"credential": _serialize_credential(credential)})

    async def revoke(self, request: Request, id: str) -> Response:
        """Revoke a passkey the current user owns."""
        user = current_user_or_none()
        if user is None:
            return _unauthorized()
        model = _maybe_credential_model()
        if model is None:
            return _webauthn_unavailable()

        pk = _parse_pk(id)
        if pk is None:
            return JsonResponse(
                {"message": "credential id must be an integer", "code": 422},
                status_code=422,
            )

        credential = await _load_own_credential(model, user, pk)
        if credential is None:
            return JsonResponse(
                {"message": "Passkey not found", "code": 404},
                status_code=404,
            )

        from pylar.database import transaction

        async with transaction():
            await model.query.where(
                model.id == pk,  # type: ignore[attr-defined]
            ).delete()
        return JsonResponse({"revoked": True, "id": pk})

    # --------------------------------------------------- internals

    def _webauthn_server(self) -> Any | None:
        try:
            from pylar.auth.webauthn import WebauthnServer
        except ImportError:
            return None
        if not self._container.has(WebauthnServer):
            return None
        return self._container.make(WebauthnServer)


# -------------------------------------------------- module helpers


def _tokenable_type_for(user: Authenticatable) -> str:
    cls = type(user)
    return f"{cls.__module__}.{cls.__qualname__}"


async def _load_user_credentials(user: Authenticatable) -> list[Any]:
    """Load every WebAuthn credential owned by *user*.

    Returns an empty list when the WebAuthn module isn't installed or
    when the user has never registered a passkey — both collapse into
    the same "no passkeys yet" state for the UI.
    """
    model = _maybe_credential_model()
    if model is None:
        return []
    rows = await model.query.where(
        (model.tokenable_type == _tokenable_type_for(user))  # type: ignore[comparison-overlap]
        & (model.tokenable_id == str(user.auth_identifier)),  # type: ignore[comparison-overlap]
    ).all()
    rows.sort(
        key=lambda c: _as_aware(c.created_at) if c.created_at else datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    return list(rows)


async def _load_own_credential(
    model: Any, user: Authenticatable, pk: int,
) -> Any | None:
    """Fetch a credential by PK *only* if it belongs to *user*.

    Returns ``None`` for missing rows and for rows that belong to a
    different user — collapsed into the same 404 so the endpoint
    doesn't leak whether the id exists on someone else's account.
    """
    from pylar.database.exceptions import RecordNotFoundError

    try:
        credential = await model.query.get(pk)
    except RecordNotFoundError:
        return None
    if credential.tokenable_type != _tokenable_type_for(user):
        return None
    if str(credential.tokenable_id) != str(user.auth_identifier):
        return None
    return credential


def _maybe_credential_model() -> Any | None:
    try:
        from pylar.auth.webauthn import WebauthnCredential
    except ImportError:
        return None
    return WebauthnCredential


def _parse_pk(raw: str) -> int | None:
    try:
        return int(raw)
    except ValueError:
        return None


async def _read_json(request: Request) -> Any:
    try:
        return await request.json()
    except (ValueError, json.JSONDecodeError):
        return {}


def _unauthorized() -> JsonResponse:
    return JsonResponse(
        {"message": "Unauthenticated", "code": 401},
        status_code=401,
    )


def _webauthn_unavailable() -> JsonResponse:
    return JsonResponse(
        {"message": "WebAuthn is not configured for this deployment", "code": 404},
        status_code=404,
    )


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _serialize_user(user: Authenticatable) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": user.auth_identifier,
    }
    for attr in ("email", "username", "name"):
        value = getattr(user, attr, None)
        if isinstance(value, str) and value:
            out[attr] = value
    return out


def _serialize_credential(credential: Any) -> dict[str, Any]:
    return {
        "id": credential.id,
        "nickname": credential.nickname,
        "aaguid": credential.aaguid,
        "transports": credential.transport_list,
        "sign_count": credential.sign_count,
        "backup_eligible": credential.backup_eligible,
        "backup_state": credential.backup_state,
        "created_at": credential.created_at.isoformat() if credential.created_at else None,
        "last_used_at": credential.last_used_at.isoformat() if credential.last_used_at else None,
    }


def _request_origin(request: Request) -> str | None:
    """Return the browser-reported origin for this request.

    Prefers the ``Origin`` header — it's what browsers set on
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
