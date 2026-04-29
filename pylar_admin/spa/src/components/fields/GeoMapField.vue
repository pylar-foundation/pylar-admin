<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '@geoman-io/leaflet-geoman-free'
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css'

/**
 * GeoMapField — render a GeoJSON column as an interactive Leaflet map.
 *
 * The map carries a single editable polygon layer representing the
 * stored geometry. When ``readonly`` is false, the Leaflet-Geoman
 * control appears in the top-left of the map with Draw / Edit /
 * Drag / Remove / Cut tools. Every ``pm:*`` event re-serialises the
 * drawn layers back to GeoJSON and pushes the string up through
 * ``update:modelValue`` so the form stays in sync. A plain
 * textarea below the map mirrors the same state for operators that
 * want to paste a canonical GeoJSON document.
 *
 * Only one feature is stored at a time: drawing a new polygon wipes
 * the previous one. Multi-feature collections are out of scope for
 * a single-column ``GeoMap`` field — use a dedicated endpoint when
 * you need more than one shape per record.
 */

interface Options {
  tile_url?: string
  attribution?: string
  center?: [number, number] | null
  zoom?: number
  height?: string
}

const props = defineProps<{
  modelValue: string | null
  readonly?: boolean
  options?: Options
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

const mapEl = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
//: One layer group holds every drawn feature so serialisation and
//: clear-on-new-draw are both single-pass operations.
let editLayer: L.FeatureGroup | null = null
const textarea = ref(props.modelValue ?? '')

const tileUrl =
  props.options?.tile_url ??
  'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const attribution =
  props.options?.attribution ??
  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
const fallbackCenter = props.options?.center ?? [55.947, 37.931]
const fallbackZoom = props.options?.zoom ?? 14

function parseGeoJson(raw: string | null): GeoJSON.GeoJsonObject | null {
  if (!raw) return null
  try {
    return JSON.parse(raw) as GeoJSON.GeoJsonObject
  } catch {
    return null
  }
}

//: Style applied to every vector Geoman / L.geoJSON produces —
//: keeps the admin look consistent with the accent colour used by
//: the rest of the admin SPA.
const LAYER_STYLE = {
  color: '#2563eb',
  weight: 2,
  fillOpacity: 0.15,
}

//: Geoman fires edit/drag/vertex events on the *layer*, not on the
//: map — so we have to attach these listeners every time a layer
//: joins ``editLayer`` (either from ``loadGeometry`` or from a fresh
//: ``pm:create``). Without this the textarea stayed stale after any
//: reshape.
const LAYER_EVENTS =
  'pm:edit pm:update pm:dragend pm:markerdragend pm:vertexadded pm:vertexremoved'

function trackLayer(layer: L.Layer) {
  layer.on(LAYER_EVENTS, emitCurrentLayers)
}

/** Render the current modelValue into the editable feature group. */
function loadGeometry() {
  if (!map || !editLayer) return
  editLayer.clearLayers()
  const geo = parseGeoJson(props.modelValue)
  if (!geo) return
  L.geoJSON(geo, { style: LAYER_STYLE }).eachLayer((layer) => {
    editLayer!.addLayer(layer)
    trackLayer(layer)
  })
  try {
    const bounds = editLayer.getBounds()
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [24, 24] })
    }
  } catch {
    /* non-polygon geometry — fit skipped */
  }
}

/** Emit whatever shapes the user has drawn as GeoJSON text. */
function emitCurrentLayers() {
  if (!editLayer) return
  const layers = editLayer.getLayers()
  if (layers.length === 0) {
    textarea.value = ''
    emit('update:modelValue', null)
    return
  }
  // One shape → emit a Feature. Multiple → FeatureCollection.
  let geojson: GeoJSON.GeoJsonObject
  if (layers.length === 1) {
    const single = (layers[0] as L.Layer & {
      toGeoJSON: () => GeoJSON.Feature
    }).toGeoJSON()
    geojson = single
  } else {
    geojson = editLayer.toGeoJSON() as GeoJSON.FeatureCollection
  }
  const encoded = JSON.stringify(geojson)
  textarea.value = encoded
  emit('update:modelValue', encoded)
}

onMounted(() => {
  if (!mapEl.value) return
  map = L.map(mapEl.value, { zoomControl: true }).setView(
    fallbackCenter,
    fallbackZoom,
  )
  L.tileLayer(tileUrl, { attribution }).addTo(map)

  editLayer = L.featureGroup().addTo(map)
  loadGeometry()

  if (!props.readonly) {
    // Mount Leaflet-Geoman controls. Only polygon, rectangle, and
    // edit/drag/remove tools are enabled — circle-marker / marker /
    // circle / cut / rotate are off because they don't map cleanly
    // to a cadastral plot contour.
    map.pm.addControls({
      position: 'topleft',
      drawMarker: false,
      drawCircleMarker: false,
      drawCircle: false,
      drawPolyline: false,
      drawText: false,
      drawPolygon: true,
      drawRectangle: true,
      editMode: true,
      dragMode: true,
      cutPolygon: false,
      removalMode: true,
      rotateMode: false,
    })
    map.pm.setGlobalOptions({
      templineStyle: LAYER_STYLE,
      hintlineStyle: { ...LAYER_STYLE, dashArray: '5,5' },
      pathOptions: LAYER_STYLE,
    })
    map.pm.setLang('ru')

    // Newly-drawn polygon wins — single-feature contract. Geoman
    // leaves the fresh layer directly on the map; moving it into
    // ``editLayer`` keeps our serialisation path uniform.
    map.on('pm:create', (e: { layer: L.Layer }) => {
      if (!editLayer || !map) return
      editLayer.clearLayers()
      map.removeLayer(e.layer)
      editLayer.addLayer(e.layer)
      trackLayer(e.layer)
      emitCurrentLayers()
    })

    // Removal Mode fires ``pm:remove`` on the map once per deleted
    // layer — reserialise what's left.
    map.on('pm:remove', () => emitCurrentLayers())
  }

  // Leaflet needs a nudge when it renders in a hidden-then-shown
  // container (e.g. inside a v-if) — one invalidateSize after mount
  // covers the common case.
  setTimeout(() => map?.invalidateSize(), 0)
})

onBeforeUnmount(() => {
  editLayer?.remove()
  map?.remove()
  map = null
  editLayer = null
})

watch(
  () => props.modelValue,
  (newVal) => {
    // Ignore the watcher fire that follows our own emit — the
    // textarea already holds the freshly-serialised string and a
    // re-load would wipe vertex handles mid-edit.
    if (newVal === textarea.value) return
    textarea.value = newVal ?? ''
    loadGeometry()
  },
)

function onTextareaInput(e: Event) {
  const value = (e.target as HTMLTextAreaElement).value
  textarea.value = value
  if (value.trim() === '') {
    emit('update:modelValue', null)
    editLayer?.clearLayers()
    return
  }
  // Push updates only when the buffer parses — prevents the map
  // from re-rendering on every keystroke before the JSON is
  // syntactically whole.
  try {
    JSON.parse(value)
    emit('update:modelValue', value)
    loadGeometry()
  } catch {
    /* wait for the user to finish typing */
  }
}
</script>

<template>
  <div class="geomap-field">
    <div
      ref="mapEl"
      class="geomap-canvas"
      :style="{ height: props.options?.height ?? '400px' }"
    ></div>
    <details v-if="!readonly" class="geomap-raw-wrap">
      <summary>GeoJSON (редактировать вручную)</summary>
      <textarea
        class="geomap-raw"
        :value="textarea"
        @input="onTextareaInput"
        spellcheck="false"
        rows="4"
        placeholder='{"type": "Feature", "geometry": {"type": "Polygon", ...}}'
      ></textarea>
    </details>
  </div>
</template>

<style scoped>
.geomap-field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.geomap-canvas {
  width: 100%;
  min-height: 200px;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-sidebar);
}

.geomap-raw-wrap {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
}

.geomap-raw-wrap > summary {
  cursor: pointer;
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
  color: var(--text-muted);
  user-select: none;
}

.geomap-raw {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: none;
  border-top: 1px solid var(--border);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8rem;
  line-height: 1.4;
  background: transparent;
  color: var(--text-primary);
  resize: vertical;
}

.geomap-raw:focus {
  outline: none;
}
</style>

<style>
/* Leaflet-Geoman's toolbar ships its own CSS that assumes a light
 * background — nudge it into the admin's palette tokens so it
 * doesn't clash on the dark variant. Unscoped deliberately: the
 * classes live outside the component subtree. */
.leaflet-pm-toolbar .leaflet-pm-icon-polygon,
.leaflet-pm-toolbar .leaflet-pm-icon-rectangle,
.leaflet-pm-toolbar .leaflet-pm-icon-edit,
.leaflet-pm-toolbar .leaflet-pm-icon-drag,
.leaflet-pm-toolbar .leaflet-pm-icon-delete {
  background-color: var(--bg-card, #fff);
}
</style>
