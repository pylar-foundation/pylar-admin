"""Tests for the admin System → Cron endpoint."""

from __future__ import annotations

import json

from pylar_admin.config import AdminConfig
from pylar_admin.controllers.api import AdminApiController
from pylar_admin.registry import AdminRegistry
from pylar.foundation.container import Container
from pylar.http import Request
from pylar.scheduling.schedule import Schedule


def _request(path: str = "/admin/api/system/schedule") -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": b"",
        "headers": [],
    })


async def test_schedule_list_empty_when_no_scheduler_bound(
    admin_config: AdminConfig,
) -> None:
    """Missing Schedule binding yields an empty list, not a 500."""
    api = AdminApiController(AdminRegistry(), admin_config)
    resp = await api.schedule_list(_request())
    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body == {"tasks": []}


async def test_schedule_list_serialises_registered_tasks(
    admin_config: AdminConfig,
) -> None:
    """Registered tasks surface with cron, name, type, and next_run_at."""
    schedule = Schedule()
    (
        schedule.command("db:backup")
        .cron("0 3 * * *")
        .name("nightly database backup")
    )

    async def _cleanup() -> None:
        return None

    schedule.call(_cleanup).cron("*/5 * * * *").timezone("Europe/Moscow")

    container = Container()
    container.instance(Schedule, schedule)
    api = AdminApiController(AdminRegistry(), admin_config, container=container)
    resp = await api.schedule_list(_request())
    assert resp.status_code == 200
    body = json.loads(resp.body)
    tasks = body["tasks"]
    assert len(tasks) == 2

    backup = tasks[0]
    assert backup["name"] == "nightly database backup"
    assert backup["cron"] == "0 3 * * *"
    assert backup["schedule_kind"] == "cron"
    assert backup["interval_seconds"] is None
    assert backup["type"] == "CommandTask"
    assert backup["timezone"] == "UTC"
    assert backup["next_run_at"] is not None

    cleanup = tasks[1]
    assert cleanup["cron"] == "*/5 * * * *"
    assert cleanup["schedule_kind"] == "cron"
    assert cleanup["timezone"] == "Europe/Moscow"
    assert cleanup["type"] == "CallableTask"


async def test_schedule_list_surfaces_interval_tasks(
    admin_config: AdminConfig,
) -> None:
    """Interval-based tasks report ``interval_seconds`` and ``schedule_kind``
    with ``cron`` nulled out so the UI knows not to render a bogus
    cron expression."""
    schedule = Schedule()
    (
        schedule.command("heartbeat")
        .every_ten_seconds()
        .name("fast heartbeat")
    )

    container = Container()
    container.instance(Schedule, schedule)
    api = AdminApiController(AdminRegistry(), admin_config, container=container)
    resp = await api.schedule_list(_request())
    body = json.loads(resp.body)
    (task,) = body["tasks"]
    assert task["schedule_kind"] == "interval"
    assert task["interval_seconds"] == 10
    assert task["cron"] is None
    assert task["next_run_at"] is not None
