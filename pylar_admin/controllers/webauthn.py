"""System → WebAuthn credentials controller (ADR-0013 phase 15c).

Surfaces the credentials stored by :class:`pylar.auth.webauthn.WebauthnServer`
so admins can see who has a passkey, who registered it when, and
revoke any credential that leaked or belongs to a departed user.

Endpoints:

* ``GET /admin/api/system/webauthn``             — list every credential
* ``DELETE /admin/api/system/webauthn/{id}``     — revoke one
* ``PATCH /admin/api/system/webauthn/{id}``      — update the nickname

The controller degrades gracefully when ``pylar[webauthn]`` is not
installed — the WebAuthn module import happens lazily and a missing
module surfaces as an empty list with a driver hint rather than a
500. This matches the admin's posture on every optional subsystem
(queues, cron, etc).
"""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime
from typing import Any

from pylar.http import JsonResponse, Request, Response


class WebauthnController:
    """Admin endpoints for managing registered WebAuthn credentials."""

    async def index(self, request: Request) -> Response:
        """Return every credential with a resolved user display label.

        The response shape is intentionally flat — one array of
        credential rows ready to paginate client-side. Tokenable
        resolution is best-effort: if the user model has been
        renamed or the row is orphaned, the label falls back to the
        raw ``tokenable_type:tokenable_id`` pair so the admin can
        still revoke.
        """
        model = _maybe_credential_model()
        if model is None:
            return JsonResponse({
                "credentials": [],
                "available": False,
            })

        rows = await model.query.all()
        # Newest-first so freshly-enrolled credentials surface at the
        # top of the list — the most common diagnostic view.
        rows.sort(
            key=lambda c: _as_aware(c.created_at) if c.created_at else datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )

        items: list[dict[str, Any]] = []
        for credential in rows:
            user_label = await _resolve_user_label(credential)
            items.append({
                "id": credential.id,
                "user": user_label,
                "tokenable_type": credential.tokenable_type,
                "tokenable_id": credential.tokenable_id,
                "nickname": credential.nickname,
                "aaguid": credential.aaguid,
                "transports": credential.transport_list,
                "sign_count": credential.sign_count,
                "backup_eligible": credential.backup_eligible,
                "backup_state": credential.backup_state,
                "created_at": _iso_or_none(credential.created_at),
                "last_used_at": _iso_or_none(credential.last_used_at),
            })

        return JsonResponse({
            "credentials": items,
            "available": True,
        })

    async def revoke(self, request: Request, id: str) -> Response:
        """Delete the credential with primary key *id*."""
        model = _maybe_credential_model()
        if model is None:
            return JsonResponse({"revoked": False}, status_code=404)

        try:
            pk = int(id)
        except ValueError:
            return JsonResponse(
                {"error": "credential id must be an integer"},
                status_code=422,
            )

        from pylar.database import transaction

        async with transaction():
            removed = await model.query.where(
                model.id == pk,  # type: ignore[attr-defined]
            ).delete()
        if not removed:
            return JsonResponse({"revoked": False}, status_code=404)
        return JsonResponse({"revoked": True, "id": pk})

    async def update(self, request: Request, id: str) -> Response:
        """Update the editable fields on a credential row (nickname only)."""
        model = _maybe_credential_model()
        if model is None:
            return JsonResponse({"updated": False}, status_code=404)

        try:
            pk = int(id)
        except ValueError:
            return JsonResponse(
                {"error": "credential id must be an integer"},
                status_code=422,
            )

        try:
            body = await request.json()
        except (ValueError, json.JSONDecodeError):
            body = {}
        nickname_raw = body.get("nickname") if isinstance(body, dict) else None
        if nickname_raw is not None and not isinstance(nickname_raw, str):
            return JsonResponse(
                {"error": "nickname must be a string or null"},
                status_code=422,
            )

        from pylar.database.exceptions import RecordNotFoundError

        try:
            credential = await model.query.get(pk)
        except RecordNotFoundError:
            return JsonResponse({"updated": False}, status_code=404)

        from pylar.database import transaction

        credential.nickname = nickname_raw or None  # type: ignore[assignment]
        async with transaction():
            await model.query.save(credential)
        return JsonResponse({
            "updated": True,
            "id": pk,
            "nickname": credential.nickname,
        })


# -------------------------------------------------- module helpers


def _maybe_credential_model() -> Any | None:
    """Import the credential model lazily so the admin stays importable
    even when ``pylar[webauthn]`` is not installed."""
    try:
        module = importlib.import_module("pylar.auth.webauthn")
    except ImportError:
        return None
    return getattr(module, "WebauthnCredential", None)


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _as_aware(value).isoformat()


async def _resolve_user_label(credential: Any) -> str:
    """Best-effort label for the credential's owner.

    We prefer a user-visible attribute (email, username, name) over
    the raw primary key. If the model can't be resolved at all (e.g.
    renamed class, orphaned row), fall back to the stored tokenable
    pair so the admin can still revoke.
    """
    qualified = str(credential.tokenable_type or "")
    module_path, _, class_name = qualified.rpartition(".")
    if not module_path or not class_name:
        return f"{credential.tokenable_type}:{credential.tokenable_id}"
    try:
        module = importlib.import_module(module_path)
    except ImportError:
        return f"{credential.tokenable_type}:{credential.tokenable_id}"
    cls = getattr(module, class_name, None)
    if cls is None:
        return f"{credential.tokenable_type}:{credential.tokenable_id}"
    try:
        user = await cls.query.where(
            cls.id == _coerce_id(str(credential.tokenable_id)),
        ).first()
    except Exception:
        return f"{credential.tokenable_type}:{credential.tokenable_id}"
    if user is None:
        return f"{credential.tokenable_type}:{credential.tokenable_id}"
    for attr in ("email", "username", "name"):
        value = getattr(user, attr, None)
        if isinstance(value, str) and value:
            return value
    return f"{credential.tokenable_type}:{credential.tokenable_id}"


def _coerce_id(raw: str) -> object:
    try:
        return int(raw)
    except ValueError:
        return raw
