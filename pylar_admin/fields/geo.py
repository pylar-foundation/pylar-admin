"""``GeoMap`` — GeoJSON field rendered as an interactive Leaflet map.

The admin treats a GeoJSON column (typically ``Feature`` / ``Polygon``)
as first-class geometry. On list views a tiny preview map renders the
contour auto-fitted to the geometry; on detail and form views the
full Leaflet instance appears with editing tools.

Tile layer defaults to OpenStreetMap (attribution-friendly, no
API key). Operators can swap in any XYZ tile URL via
:meth:`GeoMap.tiles`.
"""

from __future__ import annotations

from typing import ClassVar, Self

from pylar_admin.fields.base import Field


class GeoMap(Field):
    """Map-rendered GeoJSON column (Leaflet by default).

    ``name`` points at a column that stores the GeoJSON as text
    (``Feature``, ``FeatureCollection``, or raw ``Geometry``). The
    SPA parses the string, auto-fits the map to the geometry, and
    renders an editable vector layer so admins can adjust the shape.

    Widget options:

    * ``tile_url`` — XYZ template for the tile layer. Default is the
      standard OpenStreetMap endpoint.
    * ``center`` — ``[lat, lon]`` fallback when the geometry is empty
      (new records). ``None`` means "no fallback — show an empty
      world map and wait for input".
    * ``zoom`` — initial zoom level when falling back to ``center``.
    * ``height`` — CSS height of the map container (string like
      ``"400px"`` or ``"60vh"``). Defaults to 400 px.
    * ``attribution`` — attribution line shown in the map corner.
      Required by OSM's usage policy; leave the default unless you
      switch tile providers.
    """

    component: ClassVar[str] = "GeoMapField"

    _DEFAULT_TILE_URL = (
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    )
    _DEFAULT_ATTRIBUTION = (
        "© <a href=\"https://www.openstreetmap.org/copyright\">"
        "OpenStreetMap</a> contributors"
    )

    def __init__(self, name: str, label: str | None = None) -> None:
        super().__init__(name, label)
        self.options = {
            "tile_url": self._DEFAULT_TILE_URL,
            "attribution": self._DEFAULT_ATTRIBUTION,
            "center": None,
            "zoom": 14,
            "height": "400px",
        }
        # Full-width maps don't belong in a list-view column;
        # default to hidden there so the list stays readable. Flip
        # back with ``.show_on_index()`` when you want a mini preview.
        self.hide_from_index()

    def tiles(
        self, url: str, *, attribution: str | None = None,
    ) -> Self:
        """Override the XYZ tile layer + (optionally) attribution."""
        self.options["tile_url"] = url
        if attribution is not None:
            self.options["attribution"] = attribution
        return self

    def center(self, lat: float, lon: float, *, zoom: int = 14) -> Self:
        """Fallback centre shown when the column is empty."""
        self.options["center"] = [lat, lon]
        self.options["zoom"] = zoom
        return self

    def height(self, value: str) -> Self:
        """CSS height of the map container."""
        self.options["height"] = value
        return self

    def show_on_index(self) -> Self:
        """Opt back into rendering a small preview map in list view."""
        self.visibility.index = True
        return self
