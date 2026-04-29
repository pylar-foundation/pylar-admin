"""Primitive field types — thin wrappers around ``Field`` that pin
the SPA component and add widget-specific fluent modifiers.

Each class reads as a one-line widget spec; Nova-users will feel at
home.
"""

from __future__ import annotations

from typing import ClassVar, Self

from pylar_admin.fields.base import Field


class ID(Field):
    """Primary key — sortable and read-only by default, hidden on
    create (the database assigns it).

    Usage::

        ID.make()                # defaults to column name "id"
        ID.make("uuid")          # for UUID-keyed models
    """

    component: ClassVar[str] = "IdField"

    def __init__(
        self,
        name: str = "id",
        label: str | None = "ID",
    ) -> None:
        super().__init__(name, label)
        self.is_sortable = True
        self.is_readonly = True
        self.hide_when_creating()

    @classmethod
    def make(  # type: ignore[override]
        cls,
        name: str = "id",
        label: str | None = "ID",
    ) -> "ID":
        """Factory with a sensible default so ``ID.make()`` reads cleanly."""
        return cls(name=name, label=label)


class Text(Field):
    """Single-line text input (``<input type="text">``)."""

    component: ClassVar[str] = "TextField"

    def max_length(self, n: int) -> Self:
        return self.with_options(max_length=n)


class Textarea(Field):
    """Multi-line text input (``<textarea>``)."""

    component: ClassVar[str] = "TextareaField"

    def __init__(self, name: str, label: str | None = None) -> None:
        super().__init__(name, label)
        self.options = {"rows": 4}
        self.hide_from_index()

    def rows(self, n: int) -> Self:
        return self.with_options(rows=n)


class Email(Text):
    """``<input type="email">`` with basic format validation."""

    component: ClassVar[str] = "EmailField"


class URL(Text):
    """``<input type="url">`` — renders as a link on list views."""

    component: ClassVar[str] = "UrlField"


class Password(Text):
    """``<input type="password">`` — hidden on index + detail."""

    component: ClassVar[str] = "PasswordField"

    def __init__(self, name: str = "password", label: str | None = None) -> None:
        super().__init__(name, label)
        self.only_on_forms()


class Number(Field):
    """Numeric field — integer or decimal depending on ``decimals``."""

    component: ClassVar[str] = "NumberField"

    def __init__(self, name: str, label: str | None = None) -> None:
        super().__init__(name, label)
        self.options = {"decimals": 0, "step": 1}

    def decimals(self, n: int) -> Self:
        """Set display precision and input step accordingly."""
        step = 10 ** -n if n > 0 else 1
        self.options["decimals"] = n
        self.options["step"] = step
        return self

    def min(self, value: float) -> Self:
        return self.with_options(min=value)

    def max(self, value: float) -> Self:
        return self.with_options(max=value)


class Boolean(Field):
    """Boolean toggle — renders as a switch / checkbox."""

    component: ClassVar[str] = "BooleanField"

    def __init__(self, name: str, label: str | None = None) -> None:
        super().__init__(name, label)
        self.default_value = False


class Date(Field):
    """Date picker (``<input type="date">``) — stores ISO YYYY-MM-DD."""

    component: ClassVar[str] = "DateField"


class DateTime(Field):
    """Date + time picker — stores ISO 8601 with timezone."""

    component: ClassVar[str] = "DateTimeField"


class Markdown(Field):
    """Markdown editor on forms, rendered HTML on detail + index."""

    component: ClassVar[str] = "MarkdownField"

    def __init__(self, name: str, label: str | None = None) -> None:
        super().__init__(name, label)
        self.hide_from_index()


class Code(Field):
    """Code editor with syntax highlighting."""

    component: ClassVar[str] = "CodeField"

    def __init__(
        self, name: str, label: str | None = None, language: str = "plaintext",
    ) -> None:
        super().__init__(name, label)
        self.options = {"language": language}
        self.hide_from_index()

    def language(self, lang: str) -> Self:
        return self.with_options(language=lang)


class Json(Field):
    """Structured JSON viewer / editor.

    On list views a compact inline preview renders; on detail views
    the tree is fully expanded. Form surface is a plain
    syntax-highlighted editor.
    """

    component: ClassVar[str] = "JsonField"

    def __init__(self, name: str, label: str | None = None) -> None:
        super().__init__(name, label)
        self.hide_from_index()


class Image(Field):
    """Image URL or base64 payload — rendered inline as ``<img>``."""

    component: ClassVar[str] = "ImageField"

    def __init__(self, name: str, label: str | None = None) -> None:
        super().__init__(name, label)
        self.options = {"thumbnail_size": 64}

    def thumbnail(self, px: int) -> Self:
        return self.with_options(thumbnail_size=px)
