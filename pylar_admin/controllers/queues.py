"""System → Queues controller — Laravel Horizon parity.

Exposes read + recovery endpoints the admin SPA needs to monitor the
application's job queues:

* ``GET    /admin/api/system/queues``              — per-queue pending
                                                     backlog + policy
* ``GET    /admin/api/system/queues/failed``       — list of failed jobs
* ``POST   /admin/api/system/queues/failed/retry`` — re-queue every
                                                     failed record, or
                                                     a single one when
                                                     ``id`` is supplied
* ``DELETE /admin/api/system/queues/failed/{id}``  — forget one failure
* ``DELETE /admin/api/system/queues/failed``       — flush every failure
* ``POST   /admin/api/system/queues/{queue}/purge``— drop all pending
                                                     records from *queue*
                                                     (``clear_pending`` on
                                                     the driver — the
                                                     Protocol does not
                                                     accept a per-queue
                                                     filter, so the driver
                                                     decides how to
                                                     interpret this)

The controller talks to whatever :class:`JobQueue` is bound in the
container so MemoryQueue / DatabaseQueue / RedisQueue / SQSQueue all
work uniformly. When no queue is bound every endpoint returns empty
structures or ``queue_unavailable`` rather than 500 — the admin panel
must keep loading on apps that do not use queues at all.
"""

from __future__ import annotations

import json
from typing import Any

from pylar.foundation.container import Container
from pylar.http import JsonResponse, Request, Response


class QueueController:
    """Read-plus-remediate endpoints for the System → Queues page."""

    def __init__(self, container: Container | None = None) -> None:
        self._container = container

    # ------------------------------------------------------------- index

    async def index(self, request: Request) -> Response:
        """Return a per-queue summary: name, pending size, policy.

        The response shape mirrors what Laravel Horizon calls the
        dashboard "Queues" row — enough to render a table with one
        line per configured queue. Failure counts are global in the
        current Protocol (the failed pool is not per-queue), so they
        live on the top level.
        """
        queue = self._queue()
        queues_config = self._queues_config()
        names = queues_config.names() if queues_config is not None else ("default",)

        worker_counts: dict[str, int] = {}
        if queue is not None:
            try:
                worker_counts = await queue.worker_counts()
            except Exception:
                worker_counts = {}

        items: list[dict[str, Any]] = []
        for name in names:
            cfg = (
                queues_config.for_queue(name)
                if queues_config is not None
                else None
            )
            size = 0
            if queue is not None:
                try:
                    size = await queue.size(name)
                except Exception:
                    size = -1
            items.append({
                "name": name,
                "size": size,
                "workers": worker_counts.get(name, 0),
                "policy": {
                    "tries": cfg.tries if cfg is not None else None,
                    "timeout": cfg.timeout if cfg is not None else None,
                    "backoff": list(cfg.backoff) if cfg is not None else [],
                    "min_workers": cfg.min_workers if cfg is not None else None,
                    "max_workers": cfg.max_workers if cfg is not None else None,
                },
            })

        total_failed = 0
        if queue is not None:
            try:
                total_failed = len(await queue.failed_records())
            except Exception:
                total_failed = -1

        return JsonResponse({
            "queues": items,
            "failed_count": total_failed,
            "driver": type(queue).__name__ if queue is not None else None,
        })

    # ----------------------------------------------------------- failed

    async def failed_list(self, request: Request) -> Response:
        """Return every record currently parked in the failed pool."""
        queue = self._queue()
        if queue is None:
            return JsonResponse({"records": [], "driver": None})
        try:
            records = await queue.failed_records()
        except Exception as exc:
            return JsonResponse(
                {"error": str(exc), "driver": type(queue).__name__},
                status_code=500,
            )
        return JsonResponse({
            "records": [_serialise_failed(fj) for fj in records],
            "driver": type(queue).__name__,
        })

    async def retry_failed(self, request: Request) -> Response:
        """Re-queue one or every failed record."""
        queue = self._queue()
        if queue is None:
            return JsonResponse({"moved": 0})
        body = await _read_json(request)
        record_id = body.get("id") if isinstance(body, dict) else None
        if record_id is not None and not isinstance(record_id, str):
            return JsonResponse(
                {"error": "id must be a string"}, status_code=422,
            )
        moved = await queue.retry_failed(record_id)
        return JsonResponse({"moved": moved})

    async def forget_failed(
        self, request: Request, id: str,
    ) -> Response:
        """Drop a single failed record without re-queueing it."""
        queue = self._queue()
        if queue is None:
            return JsonResponse({"forgotten": False}, status_code=404)
        ok = await queue.forget_failed(id)
        if not ok:
            return JsonResponse({"forgotten": False}, status_code=404)
        return JsonResponse({"forgotten": True})

    async def flush_failed(self, request: Request) -> Response:
        """Drop every record in the failed pool."""
        queue = self._queue()
        if queue is None:
            return JsonResponse({"removed": 0})
        removed = await queue.flush_failed()
        return JsonResponse({"removed": removed})

    # ---------------------------------------------------------- pending

    async def pending_list(
        self, request: Request, queue_name: str,
    ) -> Response:
        """Return one page of pending records for *queue_name*.

        Query params: ``?page=N`` (1-based, default 1) and
        ``?per_page=N`` (default 25, max 200). Driver backends that
        cannot enumerate without consuming records — SQS, at the
        moment — return an empty list; the UI keys off ``driver`` to
        hint why.
        """
        queue = self._queue()
        if queue is None:
            return JsonResponse({
                "records": [],
                "driver": None,
                "meta": _page_meta(0, 1, 25),
            })
        page, per_page = _page_params(request)
        offset = (page - 1) * per_page
        try:
            total = await queue.size(queue_name)
            records = await queue.pending_records(
                queue_name, limit=per_page, offset=offset,
            )
        except Exception as exc:
            return JsonResponse(
                {"error": str(exc), "driver": type(queue).__name__},
                status_code=500,
            )
        return JsonResponse({
            "records": [_serialise_pending(r) for r in records],
            "driver": type(queue).__name__,
            "queue": queue_name,
            "meta": _page_meta(total, page, per_page),
        })

    async def job_detail(
        self, request: Request, queue_name: str, id: str,
    ) -> Response:
        """Return one job's full record — pending or failed.

        The admin job-detail page pulls this to render field-by-field
        context: payload JSON, queued_at, attempts, and — when the
        record has moved to the failed pool — the error text (which
        usually carries the Python traceback since the worker formats
        ``failed`` with ``{ExcType}: {str(exc)}\\n<traceback>``).
        """
        queue = self._queue()
        if queue is None:
            return JsonResponse(
                {"error": "queue not bound"}, status_code=404,
            )

        # Try the pending pool first.
        try:
            pending = await queue.pending_records(queue_name, limit=500)
        except Exception:
            pending = []
        for rec in pending:
            if rec.id == id:
                return JsonResponse({
                    **_serialise_pending(rec),
                    "status": "pending",
                    "error": None,
                    "completed_at": None,
                })

        # Fall back to the failed pool (carries the full traceback).
        # ``failed_at`` is surfaced as ``completed_at`` so the UI has
        # a single "Completed at" field regardless of terminal status.
        try:
            failed_records = await queue.failed_records()
        except Exception:
            failed_records = []
        for fj in failed_records:
            if fj.record.id == id:
                return JsonResponse({
                    **_serialise_failed(fj),
                    "status": "failed",
                    "payload_preview": fj.record.payload_json,
                    "completed_at": fj.failed_at.isoformat(),
                })

        # Finally the recent-history pool — catches completed and
        # cancelled jobs that have already left pending and failed.
        try:
            recent = await queue.recent_records(queue_name, limit=500)
        except Exception:
            recent = []
        for rj in recent:
            if rj.record.id == id:
                return JsonResponse({
                    **_serialise_pending(rj.record),
                    "status": rj.status,
                    "error": rj.error,
                    "completed_at": rj.completed_at.isoformat(),
                })

        return JsonResponse(
            {"error": f"job {id!r} not found in queue {queue_name!r}"},
            status_code=404,
        )

    async def cancel_pending(
        self, request: Request, queue_name: str, id: str,
    ) -> Response:
        """Drop a single pending record — admin "Cancel" button.

        Before the record is dropped we peek it so we can write a
        ``cancelled`` entry into the driver's recent-history pool.
        Without that round-trip the admin would see the job simply
        vanish from Pending without ever hitting the Recent list.
        """
        queue = self._queue()
        if queue is None:
            return JsonResponse({"cancelled": False}, status_code=404)

        # Locate the record first so we can feed ``record_completed``
        # the same JobRecord the driver is about to forget.
        target = None
        try:
            pending = await queue.pending_records(queue_name, limit=500)
        except Exception:
            pending = []
        for rec in pending:
            if rec.id == id:
                target = rec
                break

        ok = await queue.forget_pending(queue_name, id)
        if not ok:
            return JsonResponse({"cancelled": False}, status_code=404)

        if target is not None:
            try:
                await queue.record_completed(target, status="cancelled")
            except Exception:
                pass  # history is best-effort

        return JsonResponse({"cancelled": True})

    async def recent_list(
        self, request: Request, queue_name: str,
    ) -> Response:
        """Return one page of recently-terminal records for *queue_name*.

        Drives the admin panel's "Recent jobs" table — completed,
        failed, and cancelled jobs in one chronological view. Drivers
        that don't keep history return an empty list and the UI
        renders a "history not stored by this driver" hint. Same
        ``page``/``per_page`` contract as :meth:`pending_list`.
        """
        queue = self._queue()
        if queue is None:
            return JsonResponse({
                "records": [],
                "driver": None,
                "meta": _page_meta(0, 1, 25),
            })
        page, per_page = _page_params(request)
        offset = (page - 1) * per_page
        try:
            total = await queue.recent_size(queue_name)
            records = await queue.recent_records(
                queue_name, limit=per_page, offset=offset,
            )
        except Exception as exc:
            return JsonResponse(
                {"error": str(exc), "driver": type(queue).__name__},
                status_code=500,
            )
        return JsonResponse({
            "records": [_serialise_recent(r) for r in records],
            "driver": type(queue).__name__,
            "queue": queue_name,
            "meta": _page_meta(total, page, per_page),
        })

    async def purge_pending(
        self, request: Request, queue_name: str,
    ) -> Response:
        """Drop every pending (not-yet-processed) record.

        The Protocol's ``clear_pending`` is global (no per-queue
        filter), so on multi-queue drivers this purges every pending
        record across every queue. The *queue_name* path parameter
        is kept in the URL for symmetry with the UI and for future
        drivers that expose scoped clearing.
        """
        queue = self._queue()
        if queue is None:
            return JsonResponse({"removed": 0})
        removed = await queue.clear_pending()
        return JsonResponse({"removed": removed, "queue": queue_name})

    # -------------------------------------------------------- internals

    def _queue(self) -> Any:
        if self._container is None:
            return None
        try:
            from pylar.queue.queue import JobQueue
        except ImportError:
            return None
        if not self._container.has(JobQueue):
            return None
        return self._container.make(JobQueue)  # type: ignore[type-abstract]

    def _queues_config(self) -> Any:
        if self._container is None:
            return None
        try:
            from pylar.queue.config import QueuesConfig
        except ImportError:
            return None
        if not self._container.has(QueuesConfig):
            return None
        return self._container.make(QueuesConfig)


async def _read_json(request: Request) -> Any:
    try:
        return await request.json()
    except (ValueError, json.JSONDecodeError):
        return {}


#: Default page size for pending / recent tables. Matches the figure
#: called out in the admin UX spec — Horizon uses the same default.
DEFAULT_PER_PAGE = 25

#: Hard cap so a misconfigured client cannot DoS the admin API by
#: asking for a million-row page.
MAX_PER_PAGE = 200


def _page_params(request: Request) -> tuple[int, int]:
    """Parse ``?page=`` and ``?per_page=`` with sane defaults and clamps."""
    raw_page = request.query_params.get("page", "1")
    raw_per_page = request.query_params.get("per_page", str(DEFAULT_PER_PAGE))
    try:
        page = max(1, int(raw_page))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = max(1, min(int(raw_per_page), MAX_PER_PAGE))
    except (TypeError, ValueError):
        per_page = DEFAULT_PER_PAGE
    return page, per_page


def _page_meta(total: int, page: int, per_page: int) -> dict[str, int]:
    """Return the Laravel-style meta block the SPA's paginator reads."""
    if per_page <= 0:
        per_page = DEFAULT_PER_PAGE
    # At least one "page" even when empty so the UI doesn't divide by
    # zero while rendering "Page 1 of 0".
    last_page = max(1, (max(0, total) + per_page - 1) // per_page)
    return {
        "current_page": page,
        "last_page": last_page,
        "per_page": per_page,
        "total": max(0, total),
    }


def _serialise_failed(fj: Any) -> dict[str, Any]:
    """Serialise a :class:`FailedJob` into plain-JSON for the SPA.

    Receives ``Any`` because importing ``FailedJob`` at module load
    time would couple the admin package to pylar.queue, which is
    optional. The runtime shape is stable regardless.
    """
    rec = fj.record
    return {
        "id": rec.id,
        "job_class": rec.job_class,
        "queue": rec.queue,
        "attempts": rec.attempts,
        "queued_at": rec.queued_at.isoformat(),
        "available_at": rec.available_at.isoformat(),
        "error": fj.error,
        "failed_at": fj.failed_at.isoformat(),
    }


def _serialise_recent(rj: Any) -> dict[str, Any]:
    """Serialise a :class:`RecentJob` for the admin Recent table."""
    rec = rj.record
    return {
        "id": rec.id,
        "job_class": rec.job_class,
        "queue": rec.queue,
        "attempts": rec.attempts,
        "queued_at": rec.queued_at.isoformat(),
        "available_at": rec.available_at.isoformat(),
        "status": rj.status,
        "completed_at": rj.completed_at.isoformat(),
        "error": rj.error,
    }


def _serialise_pending(rec: Any) -> dict[str, Any]:
    """Serialise a :class:`JobRecord` peeked from the pending pool."""
    # ``payload_json`` is potentially large; truncate for the UI so
    # one huge payload can't flood the admin network response. The
    # full value is still one DB/Redis hop away if the operator
    # wants it.
    preview = rec.payload_json
    if isinstance(preview, str) and len(preview) > 500:
        preview = preview[:500] + "…"
    return {
        "id": rec.id,
        "job_class": rec.job_class,
        "queue": rec.queue,
        "attempts": rec.attempts,
        "queued_at": rec.queued_at.isoformat(),
        "available_at": rec.available_at.isoformat(),
        "payload_preview": preview,
    }
