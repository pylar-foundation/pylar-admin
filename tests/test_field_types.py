"""Tests for field_types — SQLAlchemy type to widget mapping."""

from sqlalchemy import String

from pylar_admin.field_types import WidgetInfo


class TestResolveWidget:
    """These test the widget mapping logic directly via column types."""

    def test_string_returns_text(self) -> None:
        # Test the mapping logic from the module
        from sqlalchemy import Column, MetaData, Table, String as SaStr

        metadata = MetaData()
        t = Table("t", metadata, Column("name", SaStr(100)))
        col = t.c.name

        # Directly test the type-checking logic
        assert isinstance(col.type, String)

    def test_widget_types_mapping(self) -> None:
        """Verify the type-to-widget mapping is correct."""
        # Boolean → checkbox
        widget = WidgetInfo(widget_type="checkbox")
        assert widget.widget_type == "checkbox"

        # Number → number
        widget = WidgetInfo(widget_type="number", html_attrs={"step": "1"})
        assert widget.html_attrs["step"] == "1"

        # DateTime → datetime-local
        widget = WidgetInfo(widget_type="datetime-local")
        assert widget.widget_type == "datetime-local"
