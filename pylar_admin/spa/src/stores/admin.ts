import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api/client'
import type {
  ModelInfo,
  ModelSchema,
  DashboardResponse,
  ModelsIndexResponse,
  MenuItem,
  MenuResponse,
} from '@/api/types'

export interface AuthUser {
  id: number | string
  name?: string
  email?: string
  is_admin?: boolean
}

export const useAdminStore = defineStore('admin', () => {
  const models = ref<ModelInfo[]>([])
  const schemas = ref<Map<string, ModelSchema>>(new Map())
  const loading = ref(false)
  const error = ref<string | null>(null)
  const siteTitle = ref('Pylar Admin')

  // Menu state — populated from /menu once per session; the sidebar
  // renders directly from this tree so routes that don't touch
  // /dashboard (e.g. System → Cron on a fresh page load) still get
  // the full model list.
  const menu = ref<MenuItem[]>([])
  const menuLoaded = ref(false)

  // Auth state.
  const user = ref<AuthUser | null>(null)
  const authChecked = ref(false)

  const modelList = computed(() => models.value)
  const isAuthenticated = computed(() => user.value !== null)

  async function checkAuth() {
    try {
      const res = await api.get<{ user: AuthUser }>('/user')
      user.value = res.user
    } catch {
      user.value = null
    } finally {
      authChecked.value = true
    }
  }

  function setUser(u: AuthUser) {
    user.value = u
    authChecked.value = true
  }

  async function logout() {
    try {
      await api.post('/logout', {})
    } catch {
      // Ignore errors on logout.
    }
    user.value = null
  }

  async function fetchMenu() {
    try {
      const res = await api.get<MenuResponse>('/menu')
      menu.value = res.items
    } catch (e: any) {
      error.value = e.body?.message || 'Failed to fetch menu'
    } finally {
      menuLoaded.value = true
    }
  }

  /** Ensure the menu is loaded exactly once per session. */
  async function ensureMenu() {
    if (menuLoaded.value) return
    await fetchMenu()
  }

  async function fetchModels() {
    loading.value = true
    error.value = null
    try {
      const res = await api.get<ModelsIndexResponse>('/models')
      models.value = res.models
    } catch (e: any) {
      error.value = e.body?.message || 'Failed to fetch models'
    } finally {
      loading.value = false
    }
  }

  async function fetchDashboard() {
    loading.value = true
    error.value = null
    try {
      const res = await api.get<DashboardResponse>('/dashboard')
      models.value = res.models
    } catch (e: any) {
      error.value = e.body?.message || 'Failed to fetch dashboard'
    } finally {
      loading.value = false
    }
  }

  async function fetchSchema(slug: string): Promise<ModelSchema | null> {
    if (schemas.value.has(slug)) return schemas.value.get(slug)!
    try {
      const schema = await api.get<ModelSchema>(`/models/${slug}/schema`)
      schemas.value.set(slug, schema)
      return schema
    } catch (e: any) {
      error.value = e.body?.message || 'Failed to fetch schema'
      return null
    }
  }

  function clearError() {
    error.value = null
  }

  return {
    models,
    schemas,
    loading,
    error,
    siteTitle,
    menu,
    menuLoaded,
    user,
    authChecked,
    modelList,
    isAuthenticated,
    checkAuth,
    setUser,
    logout,
    fetchMenu,
    ensureMenu,
    fetchModels,
    fetchDashboard,
    fetchSchema,
    clearError,
  }
})
