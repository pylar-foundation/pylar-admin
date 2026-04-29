<script setup lang="ts">
import { useAdminStore } from '@/stores/admin'

const store = useAdminStore()
</script>

<template>
  <Transition name="toast">
    <div v-if="store.error" class="toast toast-error" @click="store.clearError()">
      {{ store.error }}
      <button class="toast-close">&times;</button>
    </div>
  </Transition>
</template>

<style scoped>
.toast {
  position: fixed;
  top: 1rem;
  right: 1rem;
  padding: 0.75rem 1.25rem;
  border-radius: 8px;
  font-size: 0.875rem;
  z-index: 1000;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.toast-error {
  background: var(--color-danger);
  color: white;
}

.toast-close {
  background: none;
  border: none;
  color: white;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(2rem);
}
</style>
