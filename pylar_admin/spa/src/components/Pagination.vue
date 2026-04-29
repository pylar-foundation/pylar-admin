<script setup lang="ts">
import { computed } from 'vue'
import type { PaginationMeta } from '@/api/types'

const props = defineProps<{
  meta: PaginationMeta
}>()

const emit = defineEmits<{
  page: [page: number]
}>()

const pages = computed(() => {
  const total = props.meta.last_page
  const current = props.meta.current_page
  const range: number[] = []
  const start = Math.max(1, current - 2)
  const end = Math.min(total, current + 2)
  for (let i = start; i <= end; i++) range.push(i)
  return range
})
</script>

<template>
  <div class="pagination" v-if="meta.last_page > 1">
    <button
      class="page-btn"
      :disabled="meta.current_page <= 1"
      @click="emit('page', meta.current_page - 1)"
    >
      &laquo; Prev
    </button>

    <button
      v-for="p in pages"
      :key="p"
      class="page-btn"
      :class="{ active: p === meta.current_page }"
      @click="emit('page', p)"
    >
      {{ p }}
    </button>

    <button
      class="page-btn"
      :disabled="meta.current_page >= meta.last_page"
      @click="emit('page', meta.current_page + 1)"
    >
      Next &raquo;
    </button>

    <span class="page-info">
      {{ meta.total }} total
    </span>
  </div>
</template>

<style scoped>
.pagination {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  margin-top: 1rem;
}

.page-btn {
  padding: 0.375rem 0.75rem;
  border: 1px solid var(--border);
  background: var(--bg-primary);
  color: var(--text-secondary);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
}

.page-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-btn.active {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}

.page-info {
  margin-left: 0.75rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}
</style>
