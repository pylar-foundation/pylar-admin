"""Nova-style declarative admin fields.

Each field is a class with a fluent builder API — call
``Field.make("column")`` and chain modifiers like ``.sortable()``,
``.searchable()``, ``.readonly()``, ``.rules(...)`` until the
definition reads like the UI it produces.

Typical usage inside a ``ModelAdmin``::

    from pylar_admin import ModelAdmin
    from pylar_admin.fields import ID, Text, Number, GeoMap, DateTime

    plot_admin = ModelAdmin(
        fields=(
            ID.make(),
            Text.make("number").sortable().searchable(),
            Text.make("cadastral_number").searchable(),
            Number.make("area_sqm").decimals(2),
            GeoMap.make("contour_geojson").center(55.947, 37.931, zoom=15),
            DateTime.make("created_at").readonly().hide_from_index(),
        ),
    )

Each field class hard-codes the SPA component that renders it (via
the ``component`` class attribute) so the frontend gets a fully
specified widget spec without the caller naming strings.

Public surface intentionally small — everything a user would
touch is re-exported from this module.
"""

from __future__ import annotations

from pylar_admin.fields.base import Field, FieldVisibility
from pylar_admin.fields.geo import GeoMap
from pylar_admin.fields.simple import (
    Boolean,
    Code,
    Date,
    DateTime,
    Email,
    ID,
    Image,
    Json,
    Markdown,
    Number,
    Password,
    Text,
    Textarea,
    URL,
)

__all__ = [
    "Boolean",
    "Code",
    "Date",
    "DateTime",
    "Email",
    "Field",
    "FieldVisibility",
    "GeoMap",
    "ID",
    "Image",
    "Json",
    "Markdown",
    "Number",
    "Password",
    "Text",
    "Textarea",
    "URL",
]
