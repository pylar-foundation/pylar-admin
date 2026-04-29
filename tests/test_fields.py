"""Tests for the declarative ``pylar_admin.fields`` API."""

from __future__ import annotations

from pylar_admin import ModelAdmin
from pylar_admin.fields import (
    Boolean,
    DateTime,
    GeoMap,
    ID,
    Markdown,
    Number,
    Text,
)
from pylar_admin.registry import _apply_field_defaults


# --------------------------------------------------- base builder


def test_make_returns_instance_with_sensible_label() -> None:
    field = Text.make("cadastral_number")
    assert field.name == "cadastral_number"
    assert field.label == "Cadastral Number"


def test_explicit_label_wins() -> None:
    field = Text.make("num", label="Plot No.")
    assert field.label == "Plot No."


def test_fluent_modifiers_chain() -> None:
    field = (
        Text.make("email")
        .sortable()
        .searchable()
        .readonly()
        .nullable()
        .help("Contact address")
        .placeholder("user@example.com")
        .default("anon@example.com")
        .rules("required", "email")
    )
    assert field.is_sortable is True
    assert field.is_searchable is True
    assert field.is_readonly is True
    assert field.is_nullable is True
    assert field.help_text == "Contact address"
    assert field.placeholder_text == "user@example.com"
    assert field.default_value == "anon@example.com"
    assert field.rules_list == ["required", "email"]


def test_visibility_modifiers_flip_flags() -> None:
    only_forms = Text.make("password").only_on_forms()
    assert only_forms.visibility.index is False
    assert only_forms.visibility.detail is False
    assert only_forms.visibility.create is True
    assert only_forms.visibility.update is True

    only_index = Text.make("slug").only_on_index()
    assert only_index.visibility.index is True
    assert only_index.visibility.detail is False
    assert only_index.visibility.create is False
    assert only_index.visibility.update is False


def test_to_dict_emits_full_spec() -> None:
    spec = (
        Number.make("price")
        .decimals(2)
        .min(0)
        .sortable()
        .help("In euros")
        .to_dict()
    )
    assert spec["component"] == "NumberField"
    assert spec["sortable"] is True
    assert spec["help"] == "In euros"
    assert spec["options"]["decimals"] == 2
    assert spec["options"]["min"] == 0


# --------------------------------------------------- concrete fields


def test_id_is_sortable_readonly_hidden_on_create() -> None:
    field = ID.make()
    assert field.is_sortable is True
    assert field.is_readonly is True
    assert field.visibility.create is False


def test_boolean_defaults_to_false() -> None:
    field = Boolean.make("is_active")
    assert field.default_value is False
    assert field.component == "BooleanField"


def test_markdown_and_textarea_hide_from_index() -> None:
    md = Markdown.make("body")
    assert md.visibility.index is False
    assert md.component == "MarkdownField"


def test_number_decimals_sets_step() -> None:
    spec = Number.make("area").decimals(2).to_dict()
    assert spec["options"]["decimals"] == 2
    assert abs(spec["options"]["step"] - 0.01) < 1e-9


def test_datetime_serialises_component() -> None:
    spec = DateTime.make("created_at").readonly().to_dict()
    assert spec["component"] == "DateTimeField"
    assert spec["readonly"] is True


# ------------------------------------------------------- GeoMap


def test_geomap_defaults() -> None:
    field = GeoMap.make("contour_geojson")
    assert field.component == "GeoMapField"
    # Hidden by default on index (too heavy for a list-view column).
    assert field.visibility.index is False
    assert field.options["tile_url"].startswith("https://")
    assert "openstreetmap" in field.options["tile_url"].lower()
    assert field.options["center"] is None
    assert field.options["height"] == "400px"


def test_geomap_center_stores_lat_lon_and_zoom() -> None:
    field = GeoMap.make("shape").center(55.947, 37.931, zoom=16)
    assert field.options["center"] == [55.947, 37.931]
    assert field.options["zoom"] == 16


def test_geomap_custom_tiles_and_attribution() -> None:
    field = (
        GeoMap.make("shape")
        .tiles(
            "https://example/{z}/{x}/{y}.png",
            attribution="© Example maps",
        )
    )
    assert field.options["tile_url"] == "https://example/{z}/{x}/{y}.png"
    assert field.options["attribution"] == "© Example maps"


def test_geomap_show_on_index_opts_back_in() -> None:
    field = GeoMap.make("shape").show_on_index()
    assert field.visibility.index is True


# --------------------------------------------- ModelAdmin integration


def test_apply_field_defaults_derives_legacy_tuples() -> None:
    config = ModelAdmin(
        fields=(
            ID.make(),
            Text.make("number").sortable().searchable(),
            Text.make("cadastral_number").searchable(),
            Number.make("area_sqm").decimals(2),
            GeoMap.make("contour_geojson"),
            DateTime.make("created_at").readonly().hide_from_index(),
        ),
    )
    applied = _apply_field_defaults(config)
    # list_display drops hide_from_index + create-only fields.
    assert applied.list_display == (
        "id", "number", "cadastral_number", "area_sqm",
    )
    # search_fields picks every ``.searchable()`` field.
    assert applied.search_fields == ("number", "cadastral_number")
    # readonly_fields catches every ``.readonly()`` field.
    assert applied.readonly_fields == ("id", "created_at")
    # form_fields = union of create + update visibility.
    assert "number" in applied.form_fields
    assert "contour_geojson" in applied.form_fields


def test_explicit_legacy_tuple_overrides_declarative_default() -> None:
    config = ModelAdmin(
        list_display=("id", "number"),  # explicit override
        fields=(
            ID.make(),
            Text.make("number"),
            Text.make("address"),
        ),
    )
    applied = _apply_field_defaults(config)
    assert applied.list_display == ("id", "number")  # honoured
