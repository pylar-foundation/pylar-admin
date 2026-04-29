"""Map SQLAlchemy column types to form widget descriptors for the admin UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    Interval,
    LargeBinary,
    Numeric,
    String,
    Text,
    Time,
    Uuid,
)
from sqlalchemy import Enum as SaEnum
from sqlalchemy import JSON
from sqlalchemy.orm import ColumnProperty


@dataclass(frozen=True)
class WidgetInfo:
    """Describes how a column should be rendered in the admin form.

    The Vue.js frontend reads ``widget_type`` to pick the right component,
    ``html_attrs`` for HTML element attributes, and ``choices`` for select
    dropdowns.
    """

    widget_type: str
    html_attrs: dict[str, str] = field(default_factory=dict)
    choices: list[tuple[str, str]] | None = None


def resolve_widget(prop: ColumnProperty[object]) -> WidgetInfo:
    """Return a :class:`WidgetInfo` for the given mapped column property.

    The mapping covers every field type in ``pylar.database.fields`` plus
    raw SQLAlchemy column types.  Unknown types fall back to a plain text
    input.
    """
    col = prop.columns[0]
    sa_type = col.type

    if isinstance(sa_type, Boolean):
        return WidgetInfo(widget_type="checkbox")

    if isinstance(sa_type, SaEnum):
        members = sa_type.enums or []
        choices = [(str(m), str(m)) for m in members]
        return WidgetInfo(widget_type="select", choices=choices)

    if isinstance(sa_type, Text):
        return WidgetInfo(widget_type="textarea")

    if isinstance(sa_type, String):
        max_len = getattr(sa_type, "length", None) or 255
        return WidgetInfo(
            widget_type="text",
            html_attrs={"maxlength": str(max_len)},
        )

    if isinstance(sa_type, (Integer, BigInteger)):
        return WidgetInfo(widget_type="number", html_attrs={"step": "1"})

    if isinstance(sa_type, Numeric):
        scale = getattr(sa_type, "scale", 2) or 2
        step = f"0.{'0' * (scale - 1)}1" if scale > 0 else "1"
        return WidgetInfo(widget_type="number", html_attrs={"step": step})

    if isinstance(sa_type, Float):
        return WidgetInfo(widget_type="number", html_attrs={"step": "any"})

    if isinstance(sa_type, DateTime):
        return WidgetInfo(widget_type="datetime-local")

    if isinstance(sa_type, Date):
        return WidgetInfo(widget_type="date")

    if isinstance(sa_type, Time):
        return WidgetInfo(widget_type="time")

    if isinstance(sa_type, Interval):
        return WidgetInfo(widget_type="text", html_attrs={"placeholder": "HH:MM:SS"})

    if isinstance(sa_type, Uuid):
        return WidgetInfo(widget_type="text", html_attrs={"pattern": "[0-9a-f-]{36}"})

    if isinstance(sa_type, JSON):
        return WidgetInfo(widget_type="json")

    if isinstance(sa_type, LargeBinary):
        return WidgetInfo(widget_type="file")

    # Fallback for unknown types.
    return WidgetInfo(widget_type="text")


def column_to_field_schema(prop: ColumnProperty[object]) -> dict[str, Any]:
    """Return a JSON-serializable schema descriptor for a single column.

    Used by the admin API to send field metadata to the Vue.js frontend
    so it can render forms and tables without hard-coding column types.
    """
    col = prop.columns[0]
    widget = resolve_widget(prop)
    fks = [str(fk.target_fullname) for fk in col.foreign_keys]

    return {
        "name": prop.key,
        "type": widget.widget_type,
        "nullable": col.nullable or False,
        "primary_key": col.primary_key,
        "has_default": col.default is not None or col.server_default is not None,
        "foreign_keys": fks,
        "choices": widget.choices,
        "attrs": widget.html_attrs,
        #: The SQL ``COMMENT`` on the column — populated from
        #: ``fields.Field(comment=...)`` at class creation time.
        #: Used as a fallback label in the admin panel when no
        #: ``admin.model.<slug>.field.<name>`` translation exists.
        "comment": col.comment,
        #: Computed display label — the admin controller fills this
        #: in before shipping the payload so the frontend doesn't
        #: need access to the Translator. Priority: translation key
        #: → column comment → field name.
        "label": prop.key,
    }
