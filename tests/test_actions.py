"""Tests for admin actions (phase 12)."""

from __future__ import annotations

import csv
import io
import json

from pylar_admin.actions import (
    ActionResult,
    AdminAction,
    ExportCsvAction,
    ExportJsonAction,
    admin_action,
    resolve_actions,
)
from pylar_admin.config import AdminPermissions, ModelAdmin
from tests.conftest import Article


# ------------------------------------------------------- decorator


async def test_admin_action_decorator_attaches_metadata() -> None:
    @admin_action(name="mark_published", label="Mark as published", confirm=True)
    async def mark_published(records, *, request):  # type: ignore[no-untyped-def]
        return ActionResult.success(f"Published {len(records)} row(s).")

    assert isinstance(mark_published, AdminAction)
    assert mark_published.name == "mark_published"
    assert mark_published.label == "Mark as published"
    assert mark_published.confirm is True


async def test_admin_action_decorator_derives_label_from_name() -> None:
    @admin_action(name="feature_on_home")
    async def feature(records, *, request):  # type: ignore[no-untyped-def]
        return ActionResult.success("")

    assert feature.label == "Feature On Home"


# ----------------------------------------------------- ActionResult


async def test_action_result_file_renders_download_response() -> None:
    result = ActionResult.file(
        content=b"hello,world",
        filename="data.csv",
        content_type="text/csv",
    )
    response = result.to_response()
    assert response.status_code == 200
    assert response.media_type == "text/csv"
    assert "attachment" in response.headers.get("content-disposition", "")
    assert response.body == b"hello,world"


async def test_action_result_error_sets_400() -> None:
    response = ActionResult.error("bad").to_response()
    assert response.status_code == 400
    payload = json.loads(response.body)
    assert payload["status"] == "error"
    assert payload["message"] == "bad"


# ----------------------------------------------------- built-in exports


async def test_export_csv_action_streams_all_columns_by_default() -> None:
    class _FakeRequest:
        pass

    articles = [
        Article(id=1, title="First", body="Body A", published=True),
        Article(id=2, title="Second", body="Body B", published=False),
    ]
    result = await ExportCsvAction()(articles, request=_FakeRequest())  # type: ignore[arg-type]
    assert result.status == "download"
    assert result.content_type is not None
    assert result.content_type.startswith("text/csv")
    rows = list(csv.reader(io.StringIO(result.download.decode())))
    # Header + two data rows.
    assert len(rows) == 3
    assert "title" in rows[0]
    assert any("First" in row for row in rows[1:])


async def test_export_csv_action_respects_columns_override() -> None:
    articles = [Article(id=7, title="T", body="B", published=True)]
    result = await ExportCsvAction(columns=("id", "title"))(
        articles, request=object(),  # type: ignore[arg-type]
    )
    rows = list(csv.reader(io.StringIO(result.download.decode())))
    assert rows[0] == ["id", "title"]
    assert rows[1] == ["7", "T"]


async def test_export_json_action_uses_iso_format_for_datetimes() -> None:
    from datetime import UTC, datetime

    articles = [Article(id=1, title="T", body="B", published=True)]
    # Attach a datetime attribute to exercise the coercion path.
    articles[0].custom_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)  # type: ignore[attr-defined]
    result = await ExportJsonAction(columns=("id", "title", "custom_time"))(
        articles, request=object(),  # type: ignore[arg-type]
    )
    payload = json.loads(result.download)
    assert payload[0]["custom_time"].startswith("2026-01-01T12:00:00")


# ----------------------------------------------------- resolve_actions


async def test_resolve_actions_accepts_mixed_declaration_forms() -> None:
    @admin_action(name="decorated")
    async def decorated(records, *, request):  # type: ignore[no-untyped-def]
        return ActionResult.success("")

    async def bare(records, *, request):  # type: ignore[no-untyped-def]
        """Bare docstring summary."""
        return ActionResult.success("")

    resolved = resolve_actions((decorated, ExportCsvAction(), bare))
    names = [a.name for a in resolved]
    assert names == ["decorated", "export_csv", "bare"]
    assert resolved[2].description == "Bare docstring summary."


# ----------------------------------------------------- permissions shape


def test_admin_permissions_default_to_none() -> None:
    perms = AdminPermissions()
    assert perms.view is None
    assert perms.add is None
    assert perms.change is None
    assert perms.delete is None


def test_model_admin_carries_actions_and_permissions() -> None:
    @admin_action(name="bump")
    async def bump(records, *, request):  # type: ignore[no-untyped-def]
        return ActionResult.success("ok")

    cfg = ModelAdmin(
        actions=(bump, ExportCsvAction()),
        permissions=AdminPermissions(view="posts.view", change="posts.edit"),
    )
    assert cfg.actions == (bump, cfg.actions[1])
    assert cfg.permissions.view == "posts.view"
    assert cfg.permissions.change == "posts.edit"
    assert cfg.permissions.delete is None
