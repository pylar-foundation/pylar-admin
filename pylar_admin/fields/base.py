"""Base ``Field`` class with the Nova-style fluent builder.

A concrete field subclass only needs to set the ``component`` class
attribute (name of the SPA Vue component) and override ``__init__``
to set sensible defaults; everything else — visibility, validation,
modifiers, JSON serialization — is inherited from ``Field``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Self


@dataclass
class FieldVisibility:
    """Per-surface visibility flags — mirrors Laravel Nova's model.

    The four surfaces are the admin SPA's list view, detail view,
    create form, and update form. A field starts visible on every
    surface; modifiers like :meth:`Field.hide_from_index` or
    :meth:`Field.only_on_forms` flip individual flags.
    """

    index: bool = True
    detail: bool = True
    create: bool = True
    update: bool = True


#: Sentinel used to distinguish "not set" from "set to None" for
#: :meth:`Field.default`. Kept module-level so ``is`` comparisons
#: stay safe.
_UNSET: Any = object()


class Field:
    """Declarative admin field — abstract base for every widget type.

    Subclasses only need to set :attr:`component` (the SPA Vue
    component that renders the field) and optionally override
    :meth:`__init__` to establish widget-specific defaults. Everything
    else — the chainable modifier set, JSON serialization, visibility
    plumbing — comes from here.
    """

    #: SPA component name. Overridden per subclass so the frontend
    #: maps ``spec.component`` to a concrete Vue component without
    #: string-based indirection on the backend.
    component: ClassVar[str] = "TextField"

    def __init__(
        self,
        name: str,
        label: str | None = None,
    ) -> None:
        self.name = name
        self.label = label or _humanize(name)
        self.visibility = FieldVisibility()
        self.is_sortable: bool = False
        self.is_searchable: bool = False
        self.is_readonly: bool = False
        self.is_nullable: bool = False
        self.help_text: str | None = None
        self.placeholder_text: str | None = None
        self.default_value: Any = _UNSET
        self.rules_list: list[str] = []
        self.options: dict[str, Any] = {}

    # ------------------------------------------------------ factory

    @classmethod
    def make(cls, name: str, label: str | None = None) -> Self:
        """Fluent constructor — mirrors ``::make`` in Nova.

        Returns a fresh instance so callers can chain modifiers
        directly::

            Text.make("email").sortable().rules("required", "email")
        """
        return cls(name=name, label=label)

    # --------------------------------------------------- modifiers

    def sortable(self, flag: bool = True) -> Self:
        """Mark this column as sortable in the list view."""
        self.is_sortable = flag
        return self

    def searchable(self, flag: bool = True) -> Self:
        """Include this column in the admin's search scope."""
        self.is_searchable = flag
        return self

    def readonly(self, flag: bool = True) -> Self:
        """Render as read-only on create and update forms."""
        self.is_readonly = flag
        return self

    def nullable(self, flag: bool = True) -> Self:
        """Allow the form to submit a ``null`` value."""
        self.is_nullable = flag
        return self

    def hide_from_index(self) -> Self:
        """Do not show this field in the list view."""
        self.visibility.index = False
        return self

    def hide_from_detail(self) -> Self:
        """Do not show this field on the detail page."""
        self.visibility.detail = False
        return self

    def only_on_forms(self) -> Self:
        """Show only on create + update forms — hide list + detail."""
        self.visibility.index = False
        self.visibility.detail = False
        return self

    def only_on_index(self) -> Self:
        """Show only in the list view."""
        self.visibility.detail = False
        self.visibility.create = False
        self.visibility.update = False
        return self

    def hide_when_creating(self) -> Self:
        """Hide this field on the create form (shown on update)."""
        self.visibility.create = False
        return self

    def hide_when_updating(self) -> Self:
        """Hide this field on the update form (shown on create)."""
        self.visibility.update = False
        return self

    def help(self, text: str) -> Self:
        """Attach a help tooltip shown under the form control."""
        self.help_text = text
        return self

    def placeholder(self, text: str) -> Self:
        """Set the form control's placeholder attribute."""
        self.placeholder_text = text
        return self

    def default(self, value: Any) -> Self:
        """Pre-fill the create form with *value*."""
        self.default_value = value
        return self

    def rules(self, *rules: str) -> Self:
        """Append server-side validation rules (Laravel syntax)."""
        self.rules_list.extend(rules)
        return self

    def with_options(self, **options: Any) -> Self:
        """Merge extra widget-specific options into the spec.

        Used by subclasses to implement widget-specific chain methods
        (``GeoMap.center(...)``, ``Number.decimals(...)``, etc)
        without re-implementing builder infrastructure each time.
        """
        self.options.update(options)
        return self

    # ------------------------------------------------ serialization

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable spec consumed by the admin SPA."""
        return {
            "name": self.name,
            "label": self.label,
            "component": self.component,
            "visibility": {
                "index": self.visibility.index,
                "detail": self.visibility.detail,
                "create": self.visibility.create,
                "update": self.visibility.update,
            },
            "sortable": self.is_sortable,
            "searchable": self.is_searchable,
            "readonly": self.is_readonly,
            "nullable": self.is_nullable,
            "help": self.help_text,
            "placeholder": self.placeholder_text,
            "default": (
                None if self.default_value is _UNSET else self.default_value
            ),
            "rules": list(self.rules_list),
            "options": dict(self.options),
        }


def _humanize(snake_name: str) -> str:
    """Turn ``cadastral_number`` into ``Cadastral Number`` for labels."""
    return snake_name.replace("_", " ").strip().title()
