"""Tests for the self-service profile endpoints."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest

from pylar_admin.controllers.profile import ProfileController

from pylar.auth.context import authenticate_as
from pylar.auth.webauthn import (
    WebauthnConfig,
    WebauthnCredential,
    WebauthnServer,
)
from pylar.foundation.container import Container
from pylar.database import (
    ConnectionManager,
    DatabaseConfig,
    Model,
    fields,
    transaction,
)
from pylar.database.session import use_session
from pylar.http import Request


class _ProfileUser(Model, metaclass=type(Model)):  # type: ignore[misc]
    """Minimal Authenticatable stand-in for the profile tests."""

    class Meta:
        db_table = "profile_test_users"

    email = fields.CharField(max_length=100)
    name = fields.CharField(max_length=100)

    @property
    def auth_identifier(self) -> object:
        return self.id

    @property
    def auth_password_hash(self) -> str:
        return ""


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
            "path": "/admin/api/profile",
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


@pytest.fixture
def container() -> Container:
    c = Container()
    c.instance(WebauthnConfig, WebauthnConfig(rp_id="localhost", rp_name="Test"))
    c.singleton(WebauthnServer, WebauthnServer)
    return c




async def _make_user(email: str, name: str) -> _ProfileUser:
    async with transaction():
        user = _ProfileUser(email=email, name=name)
        await _ProfileUser.query.save(user)
        return user


async def _seed_credential(
    user: _ProfileUser, *, nickname: str = "Laptop",
) -> WebauthnCredential:
    async with transaction():
        credential = WebauthnCredential(
            tokenable_type=f"{_ProfileUser.__module__}.{_ProfileUser.__qualname__}",
            tokenable_id=str(user.id),
            credential_id=f"cred-{user.id}-{nickname}".encode(),
            public_key=b"pk",
            sign_count=0,
            transports="[]",
            backup_eligible=False,
            backup_state=False,
            nickname=nickname,
        )
        await WebauthnCredential.query.save(credential)
        return credential


# ---------------------------------------------------------------- index


async def test_index_returns_401_without_login(
    manager: ConnectionManager, container: Container,
) -> None:
    async with use_session(manager):
        resp = await ProfileController(container).index(_request())
    assert resp.status_code == 401


async def test_index_returns_own_credentials_only(
    manager: ConnectionManager, container: Container,
) -> None:
    async with use_session(manager):
        alice = await _make_user("alice@example.com", "Alice")
        bob = await _make_user("bob@example.com", "Bob")
        await _seed_credential(alice, nickname="Alice laptop")
        await _seed_credential(bob, nickname="Bob phone")

        with authenticate_as(alice):
            resp = await ProfileController(container).index(_request())

    body = json.loads(resp.body)
    assert resp.status_code == 200
    assert body["user"]["email"] == "alice@example.com"
    assert body["webauthn_available"] is True
    nicknames = {c["nickname"] for c in body["credentials"]}
    assert nicknames == {"Alice laptop"}


# -------------------------------------------------------- register


async def test_register_options_returns_challenge(
    manager: ConnectionManager, container: Container,
) -> None:
    from pylar.session.context import _reset_session, _set_session
    from pylar.session.session import Session

    async with use_session(manager):
        alice = await _make_user("alice@example.com", "Alice")
        session = Session(session_id="s1", data={})
        tok_session = _set_session(session)
        try:
            with authenticate_as(alice):
                resp = await ProfileController(container).register_options(
                    _request(),
                )
        finally:
            _reset_session(tok_session)

    body = json.loads(resp.body)
    assert resp.status_code == 200
    assert "challenge" in body
    assert body["rp"]["id"] == "localhost"
    assert body["user"]["name"] == "alice@example.com"


async def test_register_verify_requires_credential_field(
    manager: ConnectionManager, container: Container,
) -> None:
    async with use_session(manager):
        alice = await _make_user("alice@example.com", "Alice")
        with authenticate_as(alice):
            resp = await ProfileController(container).register_verify(
                _request("POST", body=b"{}"),
            )
    assert resp.status_code == 422


# --------------------------------------------------------- rename


async def test_rename_own_passkey(
    manager: ConnectionManager, container: Container,
) -> None:
    async with use_session(manager):
        alice = await _make_user("alice@example.com", "Alice")
        credential = await _seed_credential(alice, nickname="old")
        body = json.dumps({"nickname": "new name"}).encode()
        with authenticate_as(alice):
            async with transaction():
                resp = await ProfileController(container).rename(
                    _request("PATCH", body=body),
                    id=str(credential.id),
                )

    assert resp.status_code == 200
    async with use_session(manager):
        refreshed = await WebauthnCredential.query.get(credential.id)
        assert refreshed.nickname == "new name"


async def test_rename_rejects_foreign_passkey(
    manager: ConnectionManager, container: Container,
) -> None:
    async with use_session(manager):
        alice = await _make_user("alice@example.com", "Alice")
        bob = await _make_user("bob@example.com", "Bob")
        bobs_credential = await _seed_credential(bob, nickname="bob")
        body = json.dumps({"nickname": "stolen"}).encode()
        with authenticate_as(alice):
            resp = await ProfileController(container).rename(
                _request("PATCH", body=body),
                id=str(bobs_credential.id),
            )

    assert resp.status_code == 404


# ---------------------------------------------------------- revoke


async def test_revoke_own_passkey(
    manager: ConnectionManager, container: Container,
) -> None:
    async with use_session(manager):
        alice = await _make_user("alice@example.com", "Alice")
        credential = await _seed_credential(alice)
        pk = credential.id
        with authenticate_as(alice):
            async with transaction():
                resp = await ProfileController(container).revoke(
                    _request("DELETE"), id=str(pk),
                )

    assert resp.status_code == 200
    from pylar.database.exceptions import RecordNotFoundError
    async with use_session(manager):
        with pytest.raises(RecordNotFoundError):
            await WebauthnCredential.query.get(pk)


async def test_revoke_rejects_foreign_passkey(
    manager: ConnectionManager, container: Container,
) -> None:
    async with use_session(manager):
        alice = await _make_user("alice@example.com", "Alice")
        bob = await _make_user("bob@example.com", "Bob")
        bobs_credential = await _seed_credential(bob)
        with authenticate_as(alice):
            resp = await ProfileController(container).revoke(
                _request("DELETE"), id=str(bobs_credential.id),
            )

    assert resp.status_code == 404
    # Bob's credential survives.
    async with use_session(manager):
        refreshed = await WebauthnCredential.query.get(bobs_credential.id)
        assert refreshed is not None


async def test_rename_rejects_non_integer(
    manager: ConnectionManager, container: Container,
) -> None:
    async with use_session(manager):
        alice = await _make_user("alice@example.com", "Alice")
        with authenticate_as(alice):
            resp = await ProfileController(container).rename(
                _request("PATCH", body=b'{"nickname":"x"}'),
                id="abc",
            )
    assert resp.status_code == 422
