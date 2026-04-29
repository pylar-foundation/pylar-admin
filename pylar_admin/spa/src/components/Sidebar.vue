<script setup lang="ts">
import { useAdminStore } from '@/stores/admin'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { MenuLink, MenuSection } from '@/api/types'
import { SUPPORTED_LOCALES, setLocale, currentLocale, type Locale } from '@/i18n'

const store = useAdminStore()
const route = useRoute()
const router = useRouter()
const { t } = useI18n()

/** A link is active when its target route matches the current one. */
function isLinkActive(link: MenuLink): boolean {
  if (route.name !== link.route.name) return false
  const params = link.route.params ?? {}
  for (const key of Object.keys(params)) {
    if (String(route.params[key]) !== params[key]) return false
  }
  return true
}

async function onLogout() {
  await store.logout()
  router.push({ name: 'login' })
}

async function onLocaleChange(event: Event) {
  const next = (event.target as HTMLSelectElement).value as Locale
  setLocale(next)
  // Reload so the server-rendered menu labels (section names, Cron
  // description) come back translated — the full-page refresh is
  // the cheapest way to avoid keeping two sources of truth in sync.
  window.location.reload()
}
</script>

<template>
  <aside class="sidebar">
    <router-link to="/" class="sidebar-brand">
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <rect width="28" height="28" rx="6" fill="var(--accent)" />
        <text x="7" y="20" fill="white" font-size="16" font-weight="bold">P</text>
      </svg>
      <span>{{ store.siteTitle }}</span>
    </router-link>

    <nav class="sidebar-nav">
      <template v-for="(item, idx) in store.menu" :key="idx">
        <router-link
          v-if="item.kind === 'link'"
          :to="(item as MenuLink).route"
          class="nav-item"
          :class="{ active: isLinkActive(item as MenuLink) }"
          :title="(item as MenuLink).meta.description"
        >
          <span class="nav-icon">&#9632;</span>
          {{ item.label }}
        </router-link>

        <template v-else>
          <div class="nav-section">{{ (item as MenuSection).label }}</div>
          <router-link
            v-for="(child, cidx) in (item as MenuSection).items"
            :key="`${idx}-${cidx}`"
            :to="child.route"
            class="nav-item"
            :class="{ active: isLinkActive(child) }"
            :title="child.meta.description"
          >
            <span class="nav-icon">&#9654;</span>
            {{ child.label }}
          </router-link>
        </template>
      </template>
    </nav>

    <div class="sidebar-footer">
      <div class="footer-user" v-if="store.user">
        <router-link
          :to="{ name: 'profile' }"
          class="user-name user-link"
          :title="t('sidebar.profile')"
        >
          {{ store.user.email }}
        </router-link>
      </div>
      <div class="footer-actions">
        <select
          class="locale-select"
          :value="currentLocale()"
          @change="onLocaleChange"
          :title="t('sidebar.language')"
        >
          <option v-for="loc in SUPPORTED_LOCALES" :key="loc" :value="loc">
            {{ loc.toUpperCase() }}
          </option>
        </select>
        <button class="theme-toggle" @click="toggleTheme" title="Toggle dark mode">
          &#9788;
        </button>
        <button class="btn-logout" @click="onLogout" :title="t('sidebar.logout')">
          {{ t('sidebar.logout') }}
        </button>
      </div>
    </div>
  </aside>
</template>

<script lang="ts">
function toggleTheme() {
  document.documentElement.classList.toggle('dark')
  const isDark = document.documentElement.classList.contains('dark')
  localStorage.setItem('pylar-admin-theme', isDark ? 'dark' : 'light')
}

// Initialize theme from localStorage on load.
if (typeof window !== 'undefined') {
  const saved = localStorage.getItem('pylar-admin-theme')
  if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add('dark')
  }
}
</script>

<style scoped>
.sidebar {
  width: 260px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 1rem 0;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0 1.25rem 1rem;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
  text-decoration: none;
  border-bottom: 1px solid var(--border);
  margin-bottom: 0.5rem;
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem 0;
}

.nav-section {
  padding: 1rem 1.25rem 0.25rem;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  font-weight: 600;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1.25rem;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.875rem;
  border-radius: 0;
  transition: background 0.15s, color 0.15s;
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--bg-active);
  color: var(--accent);
  font-weight: 600;
}

.nav-icon {
  font-size: 0.5rem;
  opacity: 0.5;
}

.sidebar-footer {
  padding: 0.75rem 1.25rem;
  border-top: 1px solid var(--border);
}

.theme-toggle {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  font-size: 1rem;
}

.theme-toggle:hover {
  background: var(--bg-hover);
}

.footer-user {
  margin-bottom: 0.5rem;
}

.user-name {
  font-size: 0.75rem;
  color: var(--text-muted);
  word-break: break-all;
}

.user-link {
  display: inline-block;
  text-decoration: none;
  transition: color 0.12s;
}

.user-link:hover {
  color: var(--accent);
  text-decoration: underline;
}

.user-link.router-link-active {
  color: var(--accent);
}

.footer-actions {
  display: flex;
  gap: 0.5rem;
}

.btn-logout {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  font-size: 0.8rem;
}

.btn-logout:hover {
  background: var(--color-danger);
  color: white;
  border-color: var(--color-danger);
}

.locale-select {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.35rem 0.5rem;
  border-radius: 6px;
  font-size: 0.8rem;
}

.locale-select:hover {
  background: var(--bg-hover);
}
</style>
