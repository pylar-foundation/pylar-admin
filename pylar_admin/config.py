"""Admin panel configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pylar.config import BaseConfig

if TYPE_CHECKING:
    from pylar_admin.fields import Field


class AdminConfig(BaseConfig):
    """Global admin panel configuration.

    Controls the URL prefix, pagination defaults, and display options.
    Set ``enabled=False`` in your AppConfig providers list to disable the
    admin entirely — the AdminServiceProvider skips registration when
    this flag is off.
    """

    enabled: bool = True
    prefix: str = "/admin"
    site_title: str = "Pylar Admin"
    per_page: int = 25
    require_auth: bool = True


@dataclass(kw_only=True)
class ModelAdmin:
    """Per-model admin configuration.

    Controls which columns appear in the list view, which fields are
    editable, search/filter behaviour, and default ordering.  When a
    model is registered without an explicit ModelAdmin, the registry
    builds a default configuration by introspecting the SQLAlchemy mapper.

    Subclass this to customize::

        class PostAdmin(ModelAdmin):
            list_display = ("title", "published", "created_at")
            search_fields = ("title", "body")
            list_filter = ("published",)
            ordering = ("-created_at",)
    """

    #: Columns shown in the list table.  ``None`` means "all non-binary columns".
    list_display: tuple[str, ...] | None = None

    #: Columns that appear as filter controls in the sidebar.
    list_filter: tuple[str, ...] = ()

    #: Columns searched with ``ILIKE`` when the user types in the search box.
    search_fields: tuple[str, ...] = ()

    #: Fields shown on the create/edit form.  ``None`` means "all editable".
    form_fields: tuple[str, ...] | None = None

    #: Fields displayed on the form but not editable.
    readonly_fields: tuple[str, ...] = ()

    #: Default ordering.  Prefix ``-`` for descending (e.g. ``"-created_at"``).
    ordering: tuple[str, ...] = ()

    #: Nova-style declarative field list. When set, the registry
    #: derives ``list_display`` / ``search_fields`` / ``readonly_fields``
    #: / ``form_fields`` from the field specs instead of the string
    #: tuples above — one source of truth for what renders where. The
    #: old string-based API stays supported for backwards
    #: compatibility; if both are provided, the string tuples win on
    #: attributes they cover so callers can override on a case-by-case
    #: basis.
    fields: "tuple[Field, ...] | None" = None

    #: Rows per page (falls back to AdminConfig.per_page when None).
    per_page: int | None = None

    #: Human-readable singular label for this model (auto-derived when None).
    verbose_name: str | None = None

    #: Human-readable plural label (auto-derived when None).
    verbose_name_plural: str | None = None

    #: Admin actions exposed in the list view. Accepts bare callables,
    #: :func:`pylar_admin.admin_action`-decorated callables, or
    #: built-in action classes like
    #: :class:`pylar_admin.ExportCsvAction`.
    actions: tuple[object, ...] = field(default_factory=tuple)

    #: Optional permission gates — phase 11e roles/permissions. Each
    #: slot defaults to ``None`` ("no check"); set explicit codes to
    #: gate the model on :class:`pylar.auth.roles.Permission`.
    permissions: "AdminPermissions" = field(
        default_factory=lambda: AdminPermissions(),
    )


@dataclass(frozen=True, slots=True)
class AdminPermissions:
    """Permission codes required to access each verb on a model.

    All four default to ``None`` — no check, anyone with admin-session
    access can CRUD. Set explicit codes to gate a model on the
    :class:`pylar.auth.roles.Permission` surface::

        class PostAdmin(ModelAdmin):
            permissions = AdminPermissions(
                view="posts.view",
                add="posts.create",
                change="posts.edit",
                delete="posts.delete",
            )
    """

    view: str | None = None
    add: str | None = None
    change: str | None = None
    delete: str | None = None
