"""Tests for the admin System → WebAuthn credentials endpoints (phase 15c)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest

from pylar_admin.controllers.webauthn import WebauthnController

from pylar.auth.webauthn import WebauthnCredential
from pylar.database import (
    ConnectionManager,
    DatabaseConfig,
    Model,
    fields,
    transaction,
)
from pylar.database.session import use_session
from pylar.http import Request


class _WebauthnTestUser(Model, metaclass=type(Model)):  # type: ignore[misc]
    """Minimal user model for tokenable resolution in tests."""

    class Meta:
        db_table = "webauthn_admin_test_users"

    email = fields.CharField(max_length=100)
    name = fields.CharField(max_length=100)


def _request(method: str = "GET", body: bytes = b"{}") -> Request:
    sent = False

    async def _receive() -> dict[str, object]:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/admin/api/system/webauthn",
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
        },
        receive=_receive,
    )


@pytest.fixture
async def manager() -> AsyncIterator[ConnectionManager]:
    mgr = ConnectionManager(DatabaseConfig(url="sqlite+aiosqlite:///:memory:"))
    await mgr.initialize()
    async with mgr.engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)
    try:
        yield mgr
    finally:
        await mgr.dispose()


async def _seed_credential(
    *,
    tokenable_id: str = "1",
    nickname: str | None = "Work laptop",
    email: str = "alice@example.com",
) -> tuple[int, int]:
    async with transaction():
        user = _WebauthnTestUser(email=email, name="Alice")
        await _WebauthnTestUser.query.save(user)
        cred = WebauthnCredential(
            tokenable_type=(
                f"{_WebauthnTestUser.__module__}.{_WebauthnTestUser.__qualname__}"
            ),
            tokenable_id=str(user.id),
            credential_id=b"cred-" + tokenable_id.encode(),
            public_key=b"pk",
            sign_count=3,
            aaguid="00000000-0000-0000-0000-000000000042",
            transports=json.dumps(["internal", "hybrid"]),
            backup_eligible=True,
            backup_state=True,
            nickname=nickname,
        )
        await WebauthnCredential.query.save(cred)
        return int(user.id), int(cred.id)


# ---------------------------------------------------------- index


async def test_index_returns_credentials_with_resolved_user(
    manager: ConnectionManager,
) -> None:
    async with use_session(manager):
        user_id, cred_id = await _seed_credential()

        resp = await WebauthnController().index(_request())
        body = json.loads(resp.body)

    assert resp.status_code == 200
    assert body["available"] is True
    assert len(body["credentials"]) == 1
    item = body["credentials"][0]
    assert item["id"] == cred_id
    # User label prefers the email attribute.
    assert item["user"] == "alice@example.com"
    assert item["tokenable_id"] == str(user_id)
    assert item["nickname"] == "Work laptop"
    assert item["transports"] == ["internal", "hybrid"]
    assert item["backup_state"] is True
    assert item["sign_count"] == 3


async def test_index_empty_is_available_with_no_items(
    manager: ConnectionManager,
) -> None:
    async with use_session(manager):
        resp = await WebauthnController().index(_request())
        body = json.loads(resp.body)

    assert body["available"] is True
    assert body["credentials"] == []


# --------------------------------------------------------- revoke


async def test_revoke_deletes_credential(manager: ConnectionManager) -> None:
    async with use_session(manager):
        _, cred_id = await _seed_credential()
        async with transaction():
            resp = await WebauthnController().revoke(
                _request("DELETE"), id=str(cred_id),
            )
        body = json.loads(resp.body)
    assert resp.status_code == 200
    assert body == {"revoked": True, "id": cred_id}

    async with use_session(manager):
        from pylar.database.exceptions import RecordNotFoundError
        with pytest.raises(RecordNotFoundError):
            await WebauthnCredential.query.get(cred_id)


async def test_revoke_unknown_id_returns_404(manager: ConnectionManager) -> None:
    async with use_session(manager):
        resp = await WebauthnController().revoke(_request("DELETE"), id="999")
    assert resp.status_code == 404


async def test_revoke_rejects_non_integer(manager: ConnectionManager) -> None:
    resp = await WebauthnController().revoke(_request("DELETE"), id="abc")
    assert resp.status_code == 422


# --------------------------------------------------------- update


async def test_update_sets_nickname(manager: ConnectionManager) -> None:
    async with use_session(manager):
        _, cred_id = await _seed_credential(nickname=None)

        body = json.dumps({"nickname": "Primary phone"}).encode()
        async with transaction():
            resp = await WebauthnController().update(
                _request("PATCH", body=body), id=str(cred_id),
            )
        payload = json.loads(resp.body)
    assert resp.status_code == 200
    assert payload == {"updated": True, "id": cred_id, "nickname": "Primary phone"}

    async with use_session(manager):
        cred = await WebauthnCredential.query.get(cred_id)
        assert cred.nickname == "Primary phone"


async def test_update_clears_nickname_on_null(manager: ConnectionManager) -> None:
    async with use_session(manager):
        _, cred_id = await _seed_credential()

        body = json.dumps({"nickname": None}).encode()
        async with transaction():
            resp = await WebauthnController().update(
                _request("PATCH", body=body), id=str(cred_id),
            )
        payload = json.loads(resp.body)
    assert payload["nickname"] is None


async def test_update_rejects_non_string_nickname(
    manager: ConnectionManager,
) -> None:
    async with use_session(manager):
        _, cred_id = await _seed_credential()

        body = json.dumps({"nickname": 123}).encode()
        resp = await WebauthnController().update(
            _request("PATCH", body=body), id=str(cred_id),
        )
    assert resp.status_code == 422


async def test_update_unknown_id_returns_404(manager: ConnectionManager) -> None:
    async with use_session(manager):
        body = json.dumps({"nickname": "x"}).encode()
        resp = await WebauthnController().update(
            _request("PATCH", body=body), id="999",
        )
    assert resp.status_code == 404
