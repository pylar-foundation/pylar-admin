<script setup lang="ts">
import { onMounted } from 'vue'
import { useAdminStore } from '@/stores/admin'

const store = useAdminStore()

onMounted(() => {
  store.fetchDashboard()
})
</script>

<template>
  <div>
    <h1 class="page-title">Dashboard</h1>

    <div v-if="store.loading" class="loading">Loading...</div>

    <div class="card-grid" v-else>
      <router-link
        v-for="model in store.models"
        :key="model.slug"
        :to="{ name: 'model-list', params: { slug: model.slug } }"
        class="model-card"
      >
        <div class="card-count">{{ model.count ?? '—' }}</div>
        <div class="card-label">{{ model.label_plural }}</div>
      </router-link>

      <div v-if="store.models.length === 0" class="empty-state">
        No models registered. Add <code>site.register(Model)</code> in your provider.
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 1.5rem;
  color: var(--text-primary);
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}

.model-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1.5rem;
  text-decoration: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.model-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 8px var(--accent-alpha);
}

.card-count {
  font-size: 2rem;
  font-weight: 800;
  color: var(--accent);
  margin-bottom: 0.25rem;
}

.card-label {
  font-size: 0.9rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.loading {
  color: var(--text-muted);
  padding: 2rem;
}

.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}

.empty-state code {
  background: var(--bg-sidebar);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.85rem;
}
</style>
