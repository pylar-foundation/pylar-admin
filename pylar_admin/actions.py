"""Custom admin actions + built-in export helpers (phase 12).

An *admin action* is a named operation the operator can run against a
selected subset of rows in the list view. The pattern mirrors Django's
``admin.actions`` and Laravel Nova's resource actions:

* Each action has a stable machine name (``"mark_published"``), a
  human label (``"Mark as published"``), and an async callable that
  accepts the matched row collection plus the request.
* Actions are attached to a :class:`ModelAdmin` via
  ``actions = (my_action,)``.
* The API surface exposes them under
  ``POST /admin/api/models/{slug}/actions/{action_name}`` with a
  JSON body ``{"ids": [...]}``. Each controller build-out includes
  the list of registered actions on the model schema response so the
  SPA can render them.

Two built-ins ship alongside the decorator:

* :class:`ExportCsvAction` — streams selected rows as CSV.
* :class:`ExportJsonAction` — same shape, JSON body.

User-defined actions are plain async callables wrapped by
:func:`admin_action`::

    @admin_action(name="mark_published", label="Mark as published")
    async def mark_published(
        records: list[Post], *, request: Request,
    ) -> ActionResult:
        for post in records:
            post.published = True
            await Post.query.save(post)
        return ActionResult.success(f"Published {len(records)} post(s).")

The decorator attaches ``__admin_action__`` metadata so the registry
can surface actions on ``ModelAdmin.actions`` uniformly whether the
declaration used the decorator or a bare callable.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pylar.http import JsonResponse, Request, Response


# --------------------------------------------------------- result shape


@dataclass(frozen=True, slots=True)
class ActionResult:
    """What an action returns — rendered through the API layer."""

    status: str  # "success" | "error" | "download"
    message: str = ""
    #: For downloads: the raw bytes the frontend will stream to the
    #: user. ``None`` for non-download results.
    download: bytes | None = None
    #: Suggested filename for download results.
    filename: str | None = None
    #: MIME type for download results.
    content_type: str | None = None

    @classmethod
    def success(cls, message: str) -> ActionResult:
        return cls(status="success", message=message)

    @classmethod
    def error(cls, message: str) -> ActionResult:
        return cls(status="error", message=message)

    @classmethod
    def file(
        cls,
        *,
        content: bytes,
        filename: str,
        content_type: str,
    ) -> ActionResult:
        return cls(
            status="download",
            message=f"Prepared {filename}",
            download=content,
            filename=filename,
            content_type=content_type,
        )

    def to_response(self) -> Response:
        if self.status == "download" and self.download is not None:
            return Response(
                content=self.download,
                media_type=self.content_type or "application/octet-stream",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="{self.filename or "download"}"'
                    ),
                },
            )
        return JsonResponse(
            content={"status": self.status, "message": self.message},
            status_code=200 if self.status == "success" else 400,
        )


# --------------------------------------------------------- action protocol


#: Type alias — the callable every action resolves to. Accepts the
#: matched rows and the incoming request; returns a result shape the
#: controller serialises.
ActionCallable = Callable[..., Awaitable[ActionResult]]


@dataclass(frozen=True)
class AdminAction:
    """Resolved admin-action metadata + body."""

    name: str
    label: str
    handler: ActionCallable
    confirm: bool = False
    description: str = ""


def admin_action(
    *,
    name: str,
    label: str | None = None,
    confirm: bool = False,
    description: str = "",
) -> Callable[[ActionCallable], AdminAction]:
    """Decorator turning an async callable into a registered admin action.

    Usage::

        @admin_action(name="mark_published", label="Mark as published")
        async def mark_published(records, *, request):
            ...
    """

    def wrap(fn: ActionCallable) -> AdminAction:
        return AdminAction(
            name=name,
            label=label or name.replace("_", " ").title(),
            handler=fn,
            confirm=confirm,
            description=description or (fn.__doc__ or "").strip().split("\n")[0],
        )

    return wrap


# --------------------------------------------------------- built-in actions


class ExportCsvAction:
    """Stream the selected rows as a CSV file.

    Column order + names come from :attr:`ModelAdmin.list_display` so
    the export matches what the operator sees on screen. Override the
    class-level ``columns`` to export a different shape::

        class PostAdmin(ModelAdmin):
            actions = (ExportCsvAction(columns=("title", "slug", "body")),)
    """

    name: str = "export_csv"
    label: str = "Export as CSV"
    confirm: bool = False
    description: str = "Download selected rows as a CSV file."

    def __init__(self, *, columns: tuple[str, ...] | None = None) -> None:
        self._columns_override = columns

    async def __call__(
        self, records: list[Any], *, request: Request,
    ) -> ActionResult:
        columns = self._columns_override or _columns_from_records(records)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        for row in records:
            writer.writerow(
                [_coerce_csv_value(getattr(row, col, "")) for col in columns]
            )
        return ActionResult.file(
            content=buf.getvalue().encode("utf-8"),
            filename="export.csv",
            content_type="text/csv; charset=utf-8",
        )

    def as_admin_action(self) -> AdminAction:
        return AdminAction(
            name=self.name,
            label=self.label,
            handler=self.__call__,
            confirm=self.confirm,
            description=self.description,
        )


class ExportJsonAction:
    """Stream the selected rows as a JSON array.

    Uses the same column-derivation logic as CSV — override
    ``columns`` to narrow or widen the exported fields.
    """

    name: str = "export_json"
    label: str = "Export as JSON"
    confirm: bool = False
    description: str = "Download selected rows as a JSON file."

    def __init__(self, *, columns: tuple[str, ...] | None = None) -> None:
        self._columns_override = columns

    async def __call__(
        self, records: list[Any], *, request: Request,
    ) -> ActionResult:
        columns = self._columns_override or _columns_from_records(records)
        rows = [
            {col: _coerce_json_value(getattr(row, col, None)) for col in columns}
            for row in records
        ]
        content = json.dumps(rows, indent=2, ensure_ascii=False).encode("utf-8")
        return ActionResult.file(
            content=content,
            filename="export.json",
            content_type="application/json; charset=utf-8",
        )

    def as_admin_action(self) -> AdminAction:
        return AdminAction(
            name=self.name,
            label=self.label,
            handler=self.__call__,
            confirm=self.confirm,
            description=self.description,
        )


# ------------------------------------------------------------- resolution


def resolve_actions(
    declared: tuple[Any, ...],
) -> tuple[AdminAction, ...]:
    """Normalise a ``ModelAdmin.actions`` tuple into :class:`AdminAction`s.

    Accepts bare callables, :class:`AdminAction` instances produced
    by :func:`admin_action`, and the built-in action classes that
    expose :meth:`as_admin_action`. Order is preserved so the SPA
    renders actions in the order the user declared them.
    """
    resolved: list[AdminAction] = []
    for entry in declared:
        if isinstance(entry, AdminAction):
            resolved.append(entry)
            continue
        as_admin = getattr(entry, "as_admin_action", None)
        if callable(as_admin):
            resolved.append(as_admin())
            continue
        # Bare async callable — synthesise from its name + docstring.
        name = getattr(entry, "__name__", "action")
        resolved.append(
            AdminAction(
                name=name,
                label=name.replace("_", " ").title(),
                handler=entry,
                description=(entry.__doc__ or "").strip().split("\n")[0],
            )
        )
    return tuple(resolved)


# --------------------------------------------------------------- helpers


def _columns_from_records(records: list[Any]) -> tuple[str, ...]:
    """Best-effort column list when the caller didn't override."""
    if not records:
        return ()
    first = records[0]
    mapper_cols = getattr(type(first), "__table__", None)
    if mapper_cols is not None:
        return tuple(col.name for col in mapper_cols.columns)
    return tuple(sorted(k for k in first.__dict__ if not k.startswith("_")))


def _coerce_csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _coerce_json_value(value: Any) -> Any:
    """Cheap JSON coercion — datetime → isoformat, others pass through."""
    from datetime import date, datetime

    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


__all__ = [
    "ActionResult",
    "AdminAction",
    "ExportCsvAction",
    "ExportJsonAction",
    "admin_action",
    "resolve_actions",
]
