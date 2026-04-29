"""Integration tests for the admin API controller."""

from __future__ import annotations

import pytest

from pylar_admin.config import AdminConfig
from pylar_admin.controllers.api import AdminApiController
from pylar_admin.registry import AdminRegistry

from tests.conftest import Article, Tag


@pytest.fixture
def api(registry: AdminRegistry, admin_config: AdminConfig) -> AdminApiController:
    registry.register(Article)
    registry.register(Tag)
    return AdminApiController(registry, admin_config)


class TestAdminApi:
    async def test_models_index(self, api: AdminApiController) -> None:
        # Direct controller call — build a minimal Request.
        from pylar.http import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/admin/api/models",
            "query_string": b"",
            "headers": [],
        }
        request = Request(scope)
        response = await api.models_index(request)
        assert response.status_code == 200
        import json

        body = json.loads(response.body)
        slugs = [m["slug"] for m in body["models"]]
        assert "articles" in slugs
        assert "tags" in slugs

    async def test_model_schema(self, api: AdminApiController) -> None:
        from pylar.http import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/admin/api/models/articles/schema",
            "query_string": b"",
            "headers": [],
        }
        request = Request(scope)
        response = await api.model_schema(request, slug="articles")
        assert response.status_code == 200
        import json

        body = json.loads(response.body)
        assert body["slug"] == "articles"
        assert any(f["name"] == "title" for f in body["fields"])

    async def test_model_schema_not_found(self, api: AdminApiController) -> None:
        from pylar.http import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/admin/api/models/nope/schema",
            "query_string": b"",
            "headers": [],
        }
        request = Request(scope)
        response = await api.model_schema(request, slug="nope")
        assert response.status_code == 404


async def test_model_schema_field_label_prefers_translation(
    registry: AdminRegistry, admin_config: AdminConfig,
) -> None:
    """Field label priority: translator key → SQL comment → field name."""
    from pylar.foundation.container import Container
    from pylar.http import Request
    from pylar.i18n import Translator, with_locale

    from pylar_admin.controllers.api import AdminApiController

    registry.register(Article)

    container = Container()
    translator = Translator(default_locale="en", fallback_locale="en")
    translator.add_messages(
        "ru",
        {"admin.model.articles.field.title": "Заголовок"},
    )
    container.instance(Translator, translator)
    api = AdminApiController(registry, admin_config, container=container)

    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/admin/api/models/articles/schema",
        "query_string": b"",
        "headers": [],
    })

    with with_locale("ru"):
        resp = await api.model_schema(request, "articles")
    import json

    body = json.loads(resp.body)
    by_name = {f["name"]: f for f in body["fields"]}

    # Translator hit — wins even if there's no SQL comment.
    assert by_name["title"]["label"] == "Заголовок"

    # No translation, no comment — label falls back to the field name.
    assert by_name["body"]["label"] == "body"
