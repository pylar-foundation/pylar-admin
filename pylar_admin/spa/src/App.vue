<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAdminStore } from '@/stores/admin'
import Sidebar from '@/components/Sidebar.vue'
import Toast from '@/components/Toast.vue'

const store = useAdminStore()
const route = useRoute()

const isLoginPage = computed(() => route.name === 'login')
</script>

<template>
  <!-- Login page: full-screen, no sidebar -->
  <div v-if="isLoginPage" class="admin-fullscreen">
    <router-view />
  </div>

  <!-- Authenticated layout: sidebar + main -->
  <div v-else class="admin-layout">
    <Sidebar />
    <main class="admin-main">
      <Toast />
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.admin-layout {
  display: flex;
  min-height: 100vh;
}

.admin-main {
  flex: 1;
  padding: 2rem;
  background: var(--bg-primary);
  overflow-y: auto;
}

.admin-fullscreen {
  min-height: 100vh;
  background: var(--bg-primary);
}
</style>
