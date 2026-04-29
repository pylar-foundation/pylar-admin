"""Serialize SQLAlchemy model instances to JSON-safe dicts for the admin API."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import ColumnProperty

from pylar.database.model import Model


def serialize_instance(instance: Model) -> dict[str, Any]:
    """Convert a model instance to a JSON-serializable dict.

    Handles all pylar field types: datetime, date, time, timedelta,
    Decimal, UUID, Enum, bytes (omitted), and plain scalars.
    """
    mapper = sa_inspect(type(instance))
    result: dict[str, Any] = {}

    for prop in mapper.column_attrs:
        assert isinstance(prop, ColumnProperty)
        value = getattr(instance, prop.key, None)
        result[prop.key] = _to_json_value(value)

    return result


def _to_json_value(value: Any) -> Any:
    """Recursively convert a value to a JSON-safe representation."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        return None  # Binary data excluded from JSON responses.
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_to_json_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_json_value(v) for k, v in value.items()}
    return str(value)


def deserialize_form_data(
    model: type[Model],
    data: dict[str, Any],
    *,
    fields: tuple[str, ...] | None = None,
    readonly: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Parse raw form/JSON data into typed values for model attribute assignment.

    Only processes fields listed in *fields* (or all columns when None),
    skipping any in *readonly*.  Values are coerced to match the column's
    Python type.
    """
    mapper = sa_inspect(model)
    result: dict[str, Any] = {}
    allowed = set(fields) if fields is not None else None

    #: Columns managed automatically by the ORM or database — never
    #: overwritten from user input even when form_fields is None.
    auto_managed = {"created_at", "updated_at", "deleted_at"}

    for prop in mapper.column_attrs:
        assert isinstance(prop, ColumnProperty)
        name = prop.key
        if name not in data:
            continue
        if allowed is not None and name not in allowed:
            continue
        if name in readonly:
            continue
        col = prop.columns[0]
        # Skip primary keys and auto-managed timestamp columns.
        if col.primary_key:
            continue
        if name in auto_managed:
            continue

        raw = data[name]

        # Skip null/empty values for columns that have defaults —
        # let the ORM or database fill them in.
        if (raw is None or raw == "") and (
            col.default is not None or col.server_default is not None
        ):
            continue

        result[name] = _coerce(raw, col.type)

    return result


def _coerce(raw: Any, sa_type: Any) -> Any:
    """Best-effort coercion from a raw string/JSON value to the column type."""
    from sqlalchemy import (
        BigInteger,
        Boolean,
        Date,
        DateTime,
        Float,
        Integer,
        LargeBinary,
        Numeric,
        String,
        Text,
        Time,
        Uuid,
    )
    from sqlalchemy import Enum as SaEnum

    if raw is None or raw == "":
        return None

    if isinstance(sa_type, Boolean):
        if isinstance(raw, bool):
            return raw
        return str(raw).lower() in ("true", "1", "yes", "on")

    if isinstance(sa_type, (Integer, BigInteger)):
        return int(raw)

    if isinstance(sa_type, (Float, Numeric)):
        return Decimal(str(raw)) if isinstance(sa_type, Numeric) else float(raw)

    if isinstance(sa_type, DateTime):
        if isinstance(raw, datetime):
            return raw
        return datetime.fromisoformat(str(raw))

    if isinstance(sa_type, Date):
        if isinstance(raw, date):
            return raw
        return date.fromisoformat(str(raw))

    if isinstance(sa_type, Time):
        if isinstance(raw, time):
            return raw
        return time.fromisoformat(str(raw))

    if isinstance(sa_type, Uuid):
        if isinstance(raw, uuid.UUID):
            return raw
        return uuid.UUID(str(raw))

    if isinstance(sa_type, SaEnum):
        return raw

    if isinstance(sa_type, (String, Text)):
        return str(raw)

    if isinstance(sa_type, LargeBinary):
        if isinstance(raw, bytes):
            return raw
        return None

    return raw
