/** Types matching the admin JSON API responses. */

export interface ModelInfo {
  slug: string
  label: string
  label_plural: string
  count?: number
}

export interface FieldSchema {
  name: string
  /**
   * Human-readable display label. Computed server-side as
   * ``admin.model.<slug>.field.<name>`` translation → SQL
   * ``COMMENT`` → raw field name. Use this in place of ``name``
   * in table headers and form labels.
   */
  label: string
  /** Raw SQL ``COMMENT`` when present, ``null`` otherwise. */
  comment: string | null
  type: string
  nullable: boolean
  primary_key: boolean
  has_default: boolean
  foreign_keys: string[]
  choices: [string, string][] | null
  attrs: Record<string, string>
}

/**
 * Nova-style declarative field spec emitted by the backend when a
 * ``ModelAdmin`` uses ``pylar_admin.fields.*``. Each entry pins the
 * SPA component that renders the value, plus widget-specific
 * options (e.g. ``tile_url`` for ``GeoMapField``). ``null`` in
 * ``ModelSchema.field_specs`` means the admin stayed on the legacy
 * string-tuple API and the SPA should fall back to routing off
 * ``fields[].type``.
 */
export interface FieldSpec {
  name: string
  label: string
  component: string
  visibility: {
    index: boolean
    detail: boolean
    create: boolean
    update: boolean
  }
  sortable: boolean
  searchable: boolean
  readonly: boolean
  nullable: boolean
  help: string | null
  placeholder: string | null
  default: unknown
  rules: string[]
  options: Record<string, unknown>
}

export interface ModelSchema {
  slug: string
  label: string
  label_plural: string
  primary_key: string | string[]
  soft_deletes: boolean
  fields: FieldSchema[]
  field_specs: FieldSpec[] | null
  list_display: string[] | null
  list_filter: string[]
  search_fields: string[]
  form_fields: string[] | null
  readonly_fields: string[]
  ordering: string[]
  per_page: number | null
}

export interface PaginationMeta {
  current_page: number
  last_page: number
  per_page: number
  total: number
}

export interface PaginatedResponse<T> {
  data: T[]
  meta: PaginationMeta
}

export interface SingleResponse<T> {
  data: T
}

export interface DashboardResponse {
  models: ModelInfo[]
}

export interface ModelsIndexResponse {
  models: ModelInfo[]
}

export interface MenuRoute {
  name: string
  params?: Record<string, string>
}

export interface MenuLink {
  kind: 'link'
  label: string
  route: MenuRoute
  meta: Record<string, string>
}

export interface MenuSection {
  kind: 'section'
  label: string
  items: MenuLink[]
}

export type MenuItem = MenuLink | MenuSection

export interface MenuResponse {
  items: MenuItem[]
}
