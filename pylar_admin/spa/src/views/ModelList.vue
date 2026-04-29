<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { api } from '@/api/client'
import { useAdminStore } from '@/stores/admin'
import type { ModelSchema, PaginatedResponse, PaginationMeta } from '@/api/types'
import DataTable from '@/components/DataTable.vue'
import Pagination from '@/components/Pagination.vue'

const props = defineProps<{ slug: string }>()

const store = useAdminStore()
const schema = ref<ModelSchema | null>(null)
const rows = ref<Record<string, any>[]>([])
const meta = ref<PaginationMeta>({ current_page: 1, last_page: 1, per_page: 25, total: 0 })
const loading = ref(false)
const search = ref('')
const sortField = ref('')
const sortDir = ref<'asc' | 'desc'>('desc')
const page = ref(1)

async function load() {
  loading.value = true
  schema.value = await store.fetchSchema(props.slug)
  await fetchRecords()
  loading.value = false
}

async function fetchRecords() {
  const params = new URLSearchParams()
  params.set('page', String(page.value))
  if (search.value) params.set('search', search.value)
  if (sortField.value) {
    const dir = sortDir.value === 'desc' ? '-' : ''
    params.set('sort', `${dir}${sortField.value}`)
  }

  const res = await api.get<PaginatedResponse<Record<string, any>>>(
    `/models/${props.slug}/records?${params}`
  )
  rows.value = res.data
  meta.value = res.meta
}

function onSort(field: string) {
  if (sortField.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDir.value = 'asc'
  }
  page.value = 1
  fetchRecords()
}

function onPage(p: number) {
  page.value = p
  fetchRecords()
}

let searchTimeout: ReturnType<typeof setTimeout>
function onSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    page.value = 1
    fetchRecords()
  }, 300)
}

async function onDelete(pk: string) {
  if (!confirm('Are you sure you want to delete this record?')) return
  await api.del(`/models/${props.slug}/records/${pk}`)
  await fetchRecords()
}

onMounted(load)
watch(() => props.slug, load)
</script>

<template>
  <div v-if="schema">
    <div class="list-header">
      <h1 class="page-title">{{ schema.label_plural }}</h1>
      <router-link
        :to="{ name: 'model-create', params: { slug: props.slug } }"
        class="btn btn-primary"
      >
        + Create {{ schema.label }}
      </router-link>
    </div>

    <div class="toolbar">
      <input
        v-if="schema.search_fields.length > 0"
        v-model="search"
        @input="onSearch"
        type="search"
        placeholder="Search..."
        class="search-input"
      />
      <span class="record-count">{{ meta.total }} records</span>
    </div>

    <DataTable
      :fields="schema.fields"
      :rows="rows"
      :display-columns="schema.list_display"
      :sort-field="sortField"
      :sort-dir="sortDir"
      :primary-key="Array.isArray(schema.primary_key) ? schema.primary_key[0] : schema.primary_key"
      :slug="props.slug"
      @sort="onSort"
      @delete="onDelete"
    />

    <Pagination :meta="meta" @page="onPage" />
  </div>
  <div v-else class="loading">Loading...</div>
</template>

<style scoped>
.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.search-input {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 0.875rem;
  width: 280px;
}

.search-input:focus {
  outline: none;
  border-color: var(--accent);
}

.record-count {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.loading {
  color: var(--text-muted);
  padding: 2rem;
}
</style>
