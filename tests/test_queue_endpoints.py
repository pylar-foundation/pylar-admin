"""Tests for the admin System → Queues endpoints."""

from __future__ import annotations

import json

import pytest

from pylar_admin.controllers.queues import QueueController
from pylar.foundation.container import Container
from pylar.http import Request
from pylar.queue import MemoryQueue
from pylar.queue.config import QueueConfig, QueuesConfig
from pylar.queue.queue import JobQueue
from pylar.queue.record import JobRecord


def _request(
    method: str = "GET",
    path: str = "/admin/api/system/queues",
    body: bytes = b"{}",
) -> Request:
    """Build a Request whose body is readable via ``await request.json()``.

    Starlette's ``Request`` needs a ``receive`` coroutine to parse
    the body; for unit tests we hand it a one-shot coroutine that
    yields *body* and then signals disconnect.
    """
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
            "path": path,
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
        },
        receive=_receive,
    )


def _record(rid: str, queue: str = "default") -> JobRecord:
    return JobRecord(
        id=rid, job_class="tests:Dummy", payload_json="{}", queue=queue,
    )


@pytest.fixture
def container_with_queue() -> Container:
    container = Container()
    queue = MemoryQueue()
    container.instance(JobQueue, queue)
    container.instance(
        QueuesConfig,
        QueuesConfig(queues={
            "high": QueueConfig(tries=5, timeout=30, max_workers=4),
            "default": QueueConfig(),
        }),
    )
    return container


# ------------------------------------------------------ index endpoint


async def test_index_lists_queues_with_sizes_and_policy(
    container_with_queue: Container,
) -> None:
    queue = container_with_queue.make(JobQueue)
    await queue.push(_record("a", queue="default"))
    await queue.push(_record("b", queue="default"))
    await queue.push(_record("c", queue="high"))

    ctrl = QueueController(container=container_with_queue)
    resp = await ctrl.index(_request())
    body = json.loads(resp.body)

    by_name = {q["name"]: q for q in body["queues"]}
    assert by_name["default"]["size"] == 2
    assert by_name["high"]["size"] == 1
    assert by_name["high"]["policy"]["tries"] == 5
    assert by_name["high"]["policy"]["max_workers"] == 4
    assert body["driver"] == "MemoryQueue"
    assert body["failed_count"] == 0


async def test_index_without_queue_binding_returns_empty() -> None:
    container = Container()
    ctrl = QueueController(container=container)
    resp = await ctrl.index(_request())
    body = json.loads(resp.body)
    # Falls back to one synthetic "default" entry sized 0 and no driver.
    assert body["driver"] is None
    assert body["failed_count"] == 0


# --------------------------------------------------- failed pool endpoints


async def test_failed_list_surfaces_failed_records(
    container_with_queue: Container,
) -> None:
    queue = container_with_queue.make(JobQueue)
    rec = _record("f1")
    await queue.push(rec)
    popped = await queue.pop(timeout=0)
    assert popped is not None
    await queue.fail(popped, "boom")

    ctrl = QueueController(container=container_with_queue)
    resp = await ctrl.failed_list(_request())
    body = json.loads(resp.body)
    assert len(body["records"]) == 1
    entry = body["records"][0]
    assert entry["id"] == "f1"
    assert entry["error"] == "boom"
    assert "failed_at" in entry


async def test_retry_failed_moves_records_back(
    container_with_queue: Container,
) -> None:
    queue = container_with_queue.make(JobQueue)
    for rid in ("r1", "r2"):
        await queue.push(_record(rid))
        popped = await queue.pop(timeout=0)
        assert popped is not None
        await queue.fail(popped, "err")

    ctrl = QueueController(container=container_with_queue)
    resp = await ctrl.retry_failed(_request("POST"))
    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body["moved"] == 2
    # Failed pool drained, pending queue re-populated.
    assert len(await queue.failed_records()) == 0
    assert await queue.size("default") == 2


async def test_forget_failed_drops_single_record(
    container_with_queue: Container,
) -> None:
    queue = container_with_queue.make(JobQueue)
    await queue.push(_record("x"))
    popped = await queue.pop(timeout=0)
    assert popped is not None
    await queue.fail(popped, "err")

    ctrl = QueueController(container=container_with_queue)
    resp = await ctrl.forget_failed(_request("DELETE"), id="x")
    assert resp.status_code == 200
    assert json.loads(resp.body)["forgotten"] is True


async def test_forget_failed_missing_id_returns_404(
    container_with_queue: Container,
) -> None:
    ctrl = QueueController(container=container_with_queue)
    resp = await ctrl.forget_failed(_request("DELETE"), id="nope")
    assert resp.status_code == 404


async def test_flush_failed_clears_pool(
    container_with_queue: Container,
) -> None:
    queue = container_with_queue.make(JobQueue)
    for rid in ("a", "b", "c"):
        await queue.push(_record(rid))
        popped = await queue.pop(timeout=0)
        assert popped is not None
        await queue.fail(popped, "err")

    ctrl = QueueController(container=container_with_queue)
    resp = await ctrl.flush_failed(_request("DELETE"))
    body = json.loads(resp.body)
    assert body["removed"] == 3
    assert len(await queue.failed_records()) == 0


async def test_purge_pending_clears_queue(
    container_with_queue: Container,
) -> None:
    queue = container_with_queue.make(JobQueue)
    for rid in ("a", "b"):
        await queue.push(_record(rid))

    ctrl = QueueController(container=container_with_queue)
    resp = await ctrl.purge_pending(_request("POST"), queue_name="default")
    body = json.loads(resp.body)
    assert body["removed"] == 2
    assert await queue.size("default") == 0


# ----------------------------------------------- pending records listing


async def test_pending_list_returns_records(
    container_with_queue: Container,
) -> None:
    queue = container_with_queue.make(JobQueue)
    await queue.push(_record("p1"))
    await queue.push(_record("p2"))

    ctrl = QueueController(container=container_with_queue)
    resp = await ctrl.pending_list(_request(path="/admin/api/system/queues/default/pending"), queue_name="default")
    body = json.loads(resp.body)
    assert body["driver"] == "MemoryQueue"
    assert body["queue"] == "default"
    ids = [r["id"] for r in body["records"]]
    assert ids == ["p1", "p2"]
    assert "payload_preview" in body["records"][0]


async def test_pending_list_respects_per_page(
    container_with_queue: Container,
) -> None:
    queue = container_with_queue.make(JobQueue)
    for i in range(5):
        await queue.push(_record(f"p{i}"))

    ctrl = QueueController(container=container_with_queue)
    req = Request({
        "type": "http",
        "method": "GET",
        "path": "/admin/api/system/queues/default/pending",
        "query_string": b"per_page=2",
        "headers": [],
    })
    resp = await ctrl.pending_list(req, queue_name="default")
    body = json.loads(resp.body)
    assert len(body["records"]) == 2
    assert body["meta"]["per_page"] == 2
    assert body["meta"]["total"] == 5
    assert body["meta"]["current_page"] == 1
    assert body["meta"]["last_page"] == 3


async def test_pending_list_second_page_offsets(
    container_with_queue: Container,
) -> None:
    queue = container_with_queue.make(JobQueue)
    for i in range(5):
        await queue.push(_record(f"p{i}"))

    ctrl = QueueController(container=container_with_queue)
    req = Request({
        "type": "http",
        "method": "GET",
        "path": "/admin/api/system/queues/default/pending",
        "query_string": b"per_page=2&page=2",
        "headers": [],
    })
    resp = await ctrl.pending_list(req, queue_name="default")
    body = json.loads(resp.body)
    ids = [r["id"] for r in body["records"]]
    assert ids == ["p2", "p3"]
    assert body["meta"]["current_page"] == 2


async def test_pending_list_empty_without_queue_binding() -> None:
    from pylar.foundation.container import Container as _Container

    ctrl = QueueController(container=_Container())
    resp = await ctrl.pending_list(
        _request(path="/admin/api/system/queues/default/pending"),
        queue_name="default",
    )
    body = json.loads(resp.body)
    assert body["records"] == []
    assert body["driver"] is None
    assert body["meta"]["total"] == 0
    assert body["meta"]["per_page"] == 25
