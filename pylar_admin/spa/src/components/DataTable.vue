<script setup lang="ts">
import { computed } from 'vue'
import type { FieldSchema } from '@/api/types'

const props = defineProps<{
  fields: FieldSchema[]
  rows: Record<string, any>[]
  displayColumns: string[] | null
  sortField: string
  sortDir: 'asc' | 'desc'
  primaryKey: string
  slug: string
}>()

const emit = defineEmits<{
  sort: [field: string]
  delete: [pk: string]
}>()

const columns = computed(() => {
  if (props.displayColumns && props.displayColumns.length > 0) {
    return props.fields.filter((f) => props.displayColumns!.includes(f.name))
  }
  return props.fields.filter((f) => f.type !== 'file' && f.type !== 'json')
})

function sortIcon(field: string) {
  if (field !== props.sortField) return ''
  return props.sortDir === 'asc' ? ' \u2191' : ' \u2193'
}

function formatValue(value: any, field: FieldSchema): string {
  if (value === null || value === undefined) return '\u2014'
  if (field.type === 'checkbox') return value ? 'Yes' : 'No'
  if (typeof value === 'string' && value.length > 80) return value.substring(0, 80) + '\u2026'
  return String(value)
}
</script>

<template>
  <div class="table-wrap">
    <table class="data-table">
      <thead>
        <tr>
          <th
            v-for="col in columns"
            :key="col.name"
            @click="emit('sort', col.name)"
            class="sortable"
          >
            {{ col.label }}{{ sortIcon(col.name) }}
          </th>
          <th class="actions-col">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row[primaryKey]">
          <td v-for="col in columns" :key="col.name">
            {{ formatValue(row[col.name], col) }}
          </td>
          <td class="actions-col">
            <router-link
              :to="{ name: 'model-edit', params: { slug, pk: row[primaryKey] } }"
              class="btn btn-sm"
            >
              Edit
            </router-link>
            <button class="btn btn-sm btn-danger" @click="emit('delete', String(row[primaryKey]))">
              Delete
            </button>
          </td>
        </tr>
        <tr v-if="rows.length === 0">
          <td :colspan="columns.length + 1" class="empty-state">
            No records found.
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.data-table th {
  background: var(--bg-sidebar);
  padding: 0.625rem 0.75rem;
  text-align: left;
  font-weight: 600;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

.data-table th.sortable {
  cursor: pointer;
  user-select: none;
}

.data-table th.sortable:hover {
  color: var(--accent);
}

.data-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
}

.data-table tbody tr:hover {
  background: var(--bg-hover);
}

.actions-col {
  width: 150px;
  white-space: nowrap;
}

.actions-col .btn + .btn {
  margin-left: 0.25rem;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted);
}
</style>
