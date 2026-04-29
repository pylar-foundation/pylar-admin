import { createRouter, createWebHistory } from 'vue-router'
import { useAdminStore } from '@/stores/admin'
import Login from './views/Login.vue'
import Dashboard from './views/Dashboard.vue'
import ModelList from './views/ModelList.vue'
import ModelCreate from './views/ModelCreate.vue'
import ModelEdit from './views/ModelEdit.vue'
import Cron from './views/Cron.vue'
import Queues from './views/Queues.vue'
import QueueDetail from './views/QueueDetail.vue'
import JobDetail from './views/JobDetail.vue'
import Webauthn from './views/Webauthn.vue'
import Profile from './views/Profile.vue'

export const router = createRouter({
  history: createWebHistory('/admin'),
  routes: [
    { path: '/login', name: 'login', component: Login, meta: { guest: true } },
    { path: '/', name: 'dashboard', component: Dashboard },
    { path: '/models/:slug', name: 'model-list', component: ModelList, props: true },
    { path: '/models/:slug/create', name: 'model-create', component: ModelCreate, props: true },
    { path: '/models/:slug/:pk/edit', name: 'model-edit', component: ModelEdit, props: true },
    { path: '/system/cron', name: 'system-cron', component: Cron },
    { path: '/system/queues', name: 'system-queues', component: Queues },
    {
      path: '/system/queues/:queue',
      name: 'system-queue',
      component: QueueDetail,
      props: true,
    },
    {
      path: '/system/queues/:queue/:id',
      name: 'system-queue-job',
      component: JobDetail,
      props: true,
    },
    { path: '/system/webauthn', name: 'system-webauthn', component: Webauthn },
    { path: '/profile', name: 'profile', component: Profile },
  ],
})

// Auth guard — redirect to login if not authenticated.
router.beforeEach(async (to) => {
  if (to.meta.guest) return true

  const store = useAdminStore()

  // First load: check if we have a session.
  if (!store.authChecked) {
    await store.checkAuth()
  }

  if (!store.user) {
    return { name: 'login' }
  }

  // Load the menu once so the sidebar renders even on routes that
  // don't fetch dashboard data (System → Cron, direct model URLs).
  await store.ensureMenu()

  return true
})
