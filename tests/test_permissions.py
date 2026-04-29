"""Tests for admin per-model permission gating (REVIEW-5 C3)."""

from __future__ import annotations

import pytest

from pylar_admin.config import AdminConfig, AdminPermissions, ModelAdmin
from pylar_admin.controllers.api import AdminApiController
from pylar_admin.registry import AdminRegistry
from pylar.auth.context import authenticate_as
from pylar.http import Request

from tests.conftest import Article


class _FakeUser:
    """Minimal user that declares a static set of granted permission codes."""

    def __init__(self, codes: set[str]) -> None:
        self._codes = codes

    @property
    def auth_identifier(self) -> object:
        return 1

    @property
    def auth_password_hash(self) -> str:
        return ""

    async def permission_codes(self) -> set[str]:
        """Duck-typed contract consumed by ``pylar.auth.roles.has_permission``.

        When the user exposes this coroutine the helper uses the result
        directly instead of running its own SQL lookup.
        """
        return self._codes


@pytest.fixture
def gated_registry(admin_config: AdminConfig) -> AdminRegistry:
    reg = AdminRegistry()
    reg.register(
        Article,
        ModelAdmin(
            permissions=AdminPermissions(
                view="articles.view",
                add="articles.create",
                change="articles.edit",
                delete="articles.delete",
            ),
        ),
    )
    return reg


@pytest.fixture
def gated_api(
    gated_registry: AdminRegistry, admin_config: AdminConfig
) -> AdminApiController:
    return AdminApiController(gated_registry, admin_config)


def _request(method: str, path: str) -> Request:
    return Request({
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": [],
    })


async def test_view_denied_without_permission(
    gated_api: AdminApiController, db_session: None
) -> None:
    """Users without ``articles.view`` get 403 on records_index."""
    user = _FakeUser(codes=set())
    with authenticate_as(user):
        response = await gated_api.records_index(
            _request("GET", "/admin/api/models/articles/records"), "articles",
        )
    assert response.status_code == 403


async def test_view_allowed_with_permission(
    gated_api: AdminApiController, db_session: None
) -> None:
    """Users with the matching code pass the gate and get a 200."""
    user = _FakeUser(codes={"articles.view"})
    with authenticate_as(user):
        response = await gated_api.records_index(
            _request("GET", "/admin/api/models/articles/records"), "articles",
        )
    assert response.status_code == 200


async def test_delete_requires_delete_permission(
    gated_api: AdminApiController, db_session: None
) -> None:
    """Granting view only is not enough to delete."""
    user = _FakeUser(codes={"articles.view"})
    with authenticate_as(user):
        response = await gated_api.record_delete(
            _request("DELETE", "/admin/api/models/articles/records/1"),
            "articles",
            "1",
        )
    assert response.status_code == 403


async def test_anonymous_blocked(
    gated_api: AdminApiController, db_session: None
) -> None:
    """No authenticated user → 401 even if permissions would otherwise allow."""
    with authenticate_as(None):
        response = await gated_api.records_index(
            _request("GET", "/admin/api/models/articles/records"), "articles",
        )
    assert response.status_code == 401


async def test_no_permission_config_leaves_verb_open(
    registry: AdminRegistry, admin_config: AdminConfig, db_session: None
) -> None:
    """When AdminPermissions slot is None, the check is a no-op."""
    registry.register(Article)  # defaults: permissions=AdminPermissions() all None
    api = AdminApiController(registry, admin_config)
    # No authenticate_as — permission helper never consults the user.
    response = await api.records_index(
        _request("GET", "/admin/api/models/articles/records"), "articles",
    )
    assert response.status_code == 200
