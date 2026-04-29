"""Central registry of models exposed through the admin panel."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import LargeBinary, Text
from sqlalchemy.orm import ColumnProperty

from pylar_admin.config import ModelAdmin
from pylar_admin.exceptions import AdminConfigError, ModelNotRegisteredError
from pylar_admin.field_types import column_to_field_schema
from pylar.database.model import Model
from pylar.database.soft_deletes import SoftDeletes


class _Registration:
    """Internal bookkeeping for a single registered model."""

    __slots__ = ("model", "config", "slug", "label", "label_plural")

    def __init__(
        self,
        model: type[Model],
        config: ModelAdmin,
        slug: str,
        label: str,
        label_plural: str,
    ) -> None:
        self.model = model
        self.config = config
        self.slug = slug
        self.label = label
        self.label_plural = label_plural


class AdminRegistry:
    """Stores models registered for admin and provides introspection helpers.

    Typical usage from a service provider::

        registry = container.make(AdminRegistry)
        registry.register(User)
        registry.register(Post, PostAdmin())
    """

    def __init__(self) -> None:
        self._by_slug: dict[str, _Registration] = {}
        self._by_model: dict[type[Model], _Registration] = {}

    # ---------------------------------------------------------------- public API

    def register(
        self,
        model: type[Model],
        config: ModelAdmin | None = None,
    ) -> None:
        """Register *model* for admin access.

        When *config* is ``None`` a default :class:`ModelAdmin` is built by
        introspecting the model's SQLAlchemy mapper to discover columns,
        primary keys, and foreign keys.
        """
        if model in self._by_model:
            raise AdminConfigError(
                f"{model.__name__} is already registered with the admin"
            )

        effective = config if config is not None else self._auto_config(model)
        if effective.fields is not None:
            # Derive the legacy string tuples from the declarative
            # field list so the rest of the admin (list-view columns,
            # search, readonly form fields) keeps working unchanged.
            effective = _apply_field_defaults(effective)
        slug = self._make_slug(model)
        label = effective.verbose_name or _humanize(model.__name__)
        label_plural = effective.verbose_name_plural or f"{label}s"

        reg = _Registration(
            model=model,
            config=effective,
            slug=slug,
            label=label,
            label_plural=label_plural,
        )
        self._by_slug[slug] = reg
        self._by_model[model] = reg

    def unregister(self, model: type[Model]) -> None:
        reg = self._by_model.pop(model, None)
        if reg is None:
            raise ModelNotRegisteredError(model.__name__)
        self._by_slug.pop(reg.slug, None)

    def get(self, slug: str) -> _Registration:
        try:
            return self._by_slug[slug]
        except KeyError:
            raise ModelNotRegisteredError(slug) from None

    def get_for_model(self, model: type[Model]) -> _Registration:
        try:
            return self._by_model[model]
        except KeyError:
            raise ModelNotRegisteredError(model.__name__) from None

    def registered_models(self) -> tuple[type[Model], ...]:
        return tuple(r.model for r in self._by_slug.values())

    def all_registrations(self) -> tuple[_Registration, ...]:
        return tuple(self._by_slug.values())

    def model_schema(self, slug: str) -> dict[str, Any]:
        """Return a JSON-serializable schema for the Vue.js frontend."""
        reg = self.get(slug)
        mapper = sa_inspect(reg.model)
        fields_schema = []
        for prop in mapper.column_attrs:
            assert isinstance(prop, ColumnProperty)
            fields_schema.append(column_to_field_schema(prop))

        pk_cols = [c.key for c in mapper.primary_key]
        is_soft_delete = issubclass(reg.model, SoftDeletes)

        field_specs = (
            [f.to_dict() for f in reg.config.fields]
            if reg.config.fields
            else None
        )

        return {
            "slug": reg.slug,
            "label": reg.label,
            "label_plural": reg.label_plural,
            "primary_key": pk_cols[0] if len(pk_cols) == 1 else pk_cols,
            "soft_deletes": is_soft_delete,
            "fields": fields_schema,
            # ``field_specs`` is the Nova-style declarative spec the
            # SPA uses to route each field to a concrete component.
            # ``None`` when the admin still relies on the legacy
            # string-tuple API — in that case the SPA falls back to
            # picking widgets off ``fields_schema`` above.
            "field_specs": field_specs,
            "list_display": reg.config.list_display,
            "list_filter": reg.config.list_filter,
            "search_fields": reg.config.search_fields,
            "form_fields": reg.config.form_fields,
            "readonly_fields": reg.config.readonly_fields,
            "ordering": reg.config.ordering,
            "per_page": reg.config.per_page,
        }

    # -------------------------------------------------------------- internal

    def _auto_config(self, model: type[Model]) -> ModelAdmin:
        """Build a sensible default ModelAdmin by introspecting the mapper."""
        mapper = sa_inspect(model)
        all_cols: list[str] = []
        search_cols: list[str] = []
        form_cols: list[str] = []
        auto_columns = {"created_at", "updated_at", "deleted_at"}

        for prop in mapper.column_attrs:
            assert isinstance(prop, ColumnProperty)
            col = prop.columns[0]
            name = prop.key

            # Skip binary columns from list display.
            if isinstance(col.type, LargeBinary):
                continue

            all_cols.append(name)

            # String/Text columns are searchable.
            if isinstance(col.type, (Text,)) or (
                hasattr(col.type, "length") and hasattr(col.type, "impl")
            ):
                search_cols.append(name)
            elif hasattr(col.type, "length"):
                search_cols.append(name)

            # Auto-managed columns are not editable.
            if col.primary_key or name in auto_columns:
                continue
            form_cols.append(name)

        # Default ordering: -created_at if present, else -pk.
        pk_name = mapper.primary_key[0].key
        has_timestamps = "created_at" in {p.key for p in mapper.column_attrs}
        default_ordering = (f"-{pk_name}",)
        if has_timestamps:
            default_ordering = ("-created_at",)

        return ModelAdmin(
            list_display=tuple(all_cols),
            search_fields=tuple(search_cols),
            form_fields=tuple(form_cols),
            ordering=default_ordering,
        )

    def _make_slug(self, model: type[Model]) -> str:
        """Generate a URL-safe slug from the model class name."""
        name = model.__name__
        # CamelCase → kebab-case
        slug = re.sub(r"(?<=[a-z0-9])([A-Z])", r"-\1", name).lower()
        # Pluralize naively (good enough for URL slugs).
        if slug.endswith("y") and not slug.endswith(("ay", "ey", "oy", "uy")):
            slug = slug[:-1] + "ies"
        elif slug.endswith(("s", "x", "z", "ch", "sh")):
            slug += "es"
        else:
            slug += "s"
        return slug


def _humanize(class_name: str) -> str:
    """Convert CamelCase class name to a human-readable label."""
    spaced = re.sub(r"(?<=[a-z0-9])([A-Z])", r" \1", class_name)
    return spaced.strip()


def _apply_field_defaults(config: ModelAdmin) -> ModelAdmin:
    """Derive legacy string tuples from a declarative ``fields`` list.

    The Nova-style :attr:`ModelAdmin.fields` is the single source of
    truth for *which* columns appear *where* when it's set —
    visibility flags on each :class:`pylar_admin.fields.Field` map
    straight onto the legacy ``list_display`` / ``search_fields`` /
    ``readonly_fields`` / ``form_fields`` tuples the rest of the
    admin still consumes.

    String-tuple attributes already set on the config take precedence
    so callers can override a single slot without abandoning the
    declarative surface.
    """
    assert config.fields is not None  # narrow for mypy
    specs = config.fields

    def _list_display() -> tuple[str, ...]:
        return tuple(f.name for f in specs if f.visibility.index)

    def _form_fields() -> tuple[str, ...]:
        return tuple(
            f.name for f in specs
            if f.visibility.create or f.visibility.update
        )

    def _search_fields() -> tuple[str, ...]:
        return tuple(f.name for f in specs if f.is_searchable)

    def _readonly_fields() -> tuple[str, ...]:
        return tuple(f.name for f in specs if f.is_readonly)

    from dataclasses import replace

    return replace(
        config,
        list_display=config.list_display or _list_display(),
        form_fields=config.form_fields or _form_fields(),
        search_fields=config.search_fields or _search_fields(),
        readonly_fields=config.readonly_fields or _readonly_fields(),
    )
