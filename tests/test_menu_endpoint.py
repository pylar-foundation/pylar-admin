"""Tests for the admin menu endpoint (GET /admin/api/menu)."""

from __future__ import annotations

import json

from pylar_admin.config import AdminConfig
from pylar_admin.controllers.api import AdminApiController
from pylar_admin.registry import AdminRegistry
from pylar.http import Request

from tests.conftest import Article, Tag


def _request() -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/admin/api/menu",
        "query_string": b"",
        "headers": [],
    })


async def test_menu_contains_dashboard_models_and_system_sections(
    registry: AdminRegistry, admin_config: AdminConfig,
) -> None:
    """Menu response has Dashboard link + Models section + Системное section."""
    registry.register(Article)
    registry.register(Tag)
    api = AdminApiController(registry, admin_config)
    resp = await api.menu(_request())
    assert resp.status_code == 200
    body = json.loads(resp.body)
    items = body["items"]

    # Top-level structure: dashboard link, Models section, System section.
    assert len(items) == 3
    assert items[0]["kind"] == "link"
    assert items[0]["label"] == "Dashboard"
    assert items[0]["route"] == {"name": "dashboard"}

    models_section = items[1]
    assert models_section["kind"] == "section"
    assert models_section["label"] == "Models"
    model_slugs = [item["meta"]["slug"] for item in models_section["items"]]
    assert "articles" in model_slugs
    assert "tags" in model_slugs

    system_section = items[2]
    assert system_section["kind"] == "section"
    # Without an i18n Translator bound the controller falls back to
    # the English label; Russian catalogue kicks in at runtime when
    # AcceptLanguageMiddleware sets the locale to "ru".
    assert system_section["label"] == "System"
    system_labels = [item["label"] for item in system_section["items"]]
    assert "Cron" in system_labels


async def test_menu_model_links_use_model_list_route(
    registry: AdminRegistry, admin_config: AdminConfig,
) -> None:
    """Each registered model produces a vue-router compatible link."""
    registry.register(Article)
    api = AdminApiController(registry, admin_config)
    resp = await api.menu(_request())
    body = json.loads(resp.body)

    models_section = body["items"][1]
    article_link = next(
        it for it in models_section["items"] if it["meta"]["slug"] == "articles"
    )
    assert article_link["route"]["name"] == "model-list"
    assert article_link["route"]["params"] == {"slug": "articles"}


async def test_menu_system_cron_carries_description_meta(
    admin_config: AdminConfig,
) -> None:
    """The Cron entry exposes a human-readable description in meta."""
    api = AdminApiController(AdminRegistry(), admin_config)
    resp = await api.menu(_request())
    body = json.loads(resp.body)
    cron_entry = body["items"][2]["items"][0]
    assert cron_entry["meta"]["description"]


async def test_menu_translates_labels_when_translator_is_bound(
    registry: AdminRegistry, admin_config: AdminConfig,
) -> None:
    """With a Translator in the container and locale=ru, labels come in Russian."""
    from pylar.foundation.container import Container
    from pylar.i18n import Translator, with_locale

    from pylar_admin.provider import AdminServiceProvider

    # Minimal container with the admin's own translations loaded
    # via the provider's helper.
    container = Container()
    translator = Translator(default_locale="en", fallback_locale="en")
    container.instance(Translator, translator)
    AdminServiceProvider._merge_admin_translations(container)

    registry.register(Article)
    api = AdminApiController(registry, admin_config, container=container)

    with with_locale("ru"):
        resp = await api.menu(_request())
    body = json.loads(resp.body)
    items = body["items"]

    assert items[0]["label"] == "Панель"
    assert items[1]["label"] == "Модели"
    assert items[2]["label"] == "Системное"
    assert items[2]["items"][0]["label"] == "Расписание"


async def test_model_labels_use_translator_with_fallback_to_label_plural(
    registry: AdminRegistry, admin_config: AdminConfig,
) -> None:
    """Model menu entries consult ``admin.model.<slug>.plural`` first;
    when the key is missing they fall back to ModelAdmin's label_plural."""
    from pylar.foundation.container import Container
    from pylar.i18n import Translator, with_locale

    container = Container()
    translator = Translator(default_locale="en", fallback_locale="en")
    # Only translate articles — tags has no key so it should fall back.
    translator.add_messages("ru", {
        "admin.model.articles.plural": "Статьи",
        "admin.model.articles.singular": "Статья",
    })
    container.instance(Translator, translator)

    registry.register(Article)
    registry.register(Tag)
    api = AdminApiController(registry, admin_config, container=container)

    with with_locale("ru"):
        resp = await api.menu(_request())
    body = json.loads(resp.body)
    model_items = body["items"][1]["items"]

    by_slug = {item["meta"]["slug"]: item for item in model_items}
    # Translated:
    assert by_slug["articles"]["label"] == "Статьи"
    assert by_slug["articles"]["meta"]["label_singular"] == "Статья"
    # Untranslated — falls back to ModelAdmin-derived label:
    assert by_slug["tags"]["label"] == "Tags"
    assert by_slug["tags"]["meta"]["label_singular"] == "Tag"
