<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '@/api/client'

const props = defineProps<{ queue: string }>()

const { t } = useI18n()

interface PendingRecord {
  id: string
  job_class: string
  queue: string
  attempts: number
  queued_at: string
  available_at: string
  payload_preview: string
}

interface PageMeta {
  current_page: number
  last_page: number
  per_page: number
  total: number
}

interface PendingResponse {
  records: PendingRecord[]
  driver: string | null
  queue: string
  meta: PageMeta
}

interface RecentRecord {
  id: string
  job_class: string
  queue: string
  attempts: number
  queued_at: string
  available_at: string
  status: 'completed' | 'failed' | 'cancelled'
  completed_at: string
  error: string | null
}

interface RecentResponse {
  records: RecentRecord[]
  driver: string | null
  meta: PageMeta
}

const PER_PAGE = 25

function emptyMeta(): PageMeta {
  return { current_page: 1, last_page: 1, per_page: PER_PAGE, total: 0 }
}

const records = ref<PendingRecord[]>([])
const recent = ref<RecentRecord[]>([])
const pendingMeta = ref<PageMeta>(emptyMeta())
const recentMeta = ref<PageMeta>(emptyMeta())
const pendingPage = ref(1)
const recentPage = ref(1)
const driver = ref<string | null>(null)
const loading = ref(true)
const error = ref('')

async function loadPending() {
  const qs = `page=${pendingPage.value}&per_page=${PER_PAGE}`
  const p = await api.get<PendingResponse>(
    `/system/queues/${encodeURIComponent(props.queue)}/pending?${qs}`,
  )
  records.value = p.records
  pendingMeta.value = p.meta ?? emptyMeta()
  driver.value = p.driver
}

async function loadRecent() {
  const qs = `page=${recentPage.value}&per_page=${PER_PAGE}`
  const r = await api.get<RecentResponse>(
    `/system/queues/${encodeURIComponent(props.queue)}/recent?${qs}`,
  )
  recent.value = r.records
  recentMeta.value = r.meta ?? emptyMeta()
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    await Promise.all([loadPending(), loadRecent()])
  } catch (e: any) {
    error.value = e.body?.message || t('queues.load_failed')
  } finally {
    loading.value = false
  }
}

async function goPending(page: number) {
  if (page < 1 || page > pendingMeta.value.last_page) return
  pendingPage.value = page
  try {
    await loadPending()
  } catch (e: any) {
    error.value = e.body?.message || t('queues.load_failed')
  }
}

async function goRecent(page: number) {
  if (page < 1 || page > recentMeta.value.last_page) return
  recentPage.value = page
  try {
    await loadRecent()
  } catch (e: any) {
    error.value = e.body?.message || t('queues.load_failed')
  }
}

function formatTimestamp(iso: string): string {
  const dt = new Date(iso)
  return Number.isNaN(dt.getTime())
    ? iso
    : dt.toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      })
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <router-link :to="{ name: 'system-queues' }" class="back-link">
          ← {{ t('queues.back_to_queues') }}
        </router-link>
        <h1 class="page-title">{{ queue }}</h1>
        <div class="driver-line">
          {{ t('queues.driver') }}: <code>{{ driver ?? '—' }}</code>
        </div>
      </div>
      <button class="btn-refresh" @click="load" :disabled="loading">
        {{ loading ? t('cron.refreshing') : t('cron.refresh') }}
      </button>
    </div>

    <div v-if="loading && records.length === 0 && recent.length === 0" class="loading">
      {{ t('cron.loading') }}
    </div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <!-- Pending ------------------------------------------------------ -->
    <section class="card">
      <h2 class="section-title">
        {{ t('queues.section_pending') }}
        <span v-if="pendingMeta.total" class="count">{{ pendingMeta.total }}</span>
      </h2>
      <div v-if="records.length === 0" class="empty-state-inline">
        {{ t('queues.pending_empty') }}
      </div>
      <table v-else class="table">
        <thead>
          <tr>
            <th>{{ t('queues.col_job') }}</th>
            <th>{{ t('queues.col_status') }}</th>
            <th class="num">{{ t('queues.col_attempts') }}</th>
            <th>{{ t('queues.col_queued_at') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in records"
            :key="r.id"
            class="clickable"
            @click="$router.push({
              name: 'system-queue-job',
              params: { queue, id: r.id },
            })"
          >
            <td>
              <div class="strong mono tiny">{{ r.job_class }}</div>
              <div class="muted tiny">{{ r.id }}</div>
            </td>
            <td>
              <span class="status-pill status-pending">
                {{ t('queues.status_pending') }}
              </span>
            </td>
            <td class="num muted">{{ r.attempts }}</td>
            <td class="muted tiny">{{ formatTimestamp(r.queued_at) }}</td>
            <td class="muted">→</td>
          </tr>
        </tbody>
      </table>
      <div v-if="pendingMeta.last_page > 1" class="pager">
        <button
          class="btn-page"
          :disabled="pendingMeta.current_page <= 1"
          @click="goPending(pendingMeta.current_page - 1)"
        >
          ← {{ t('queues.page_prev') }}
        </button>
        <span class="pager-info">
          {{ t('queues.page_of', {
            current: pendingMeta.current_page,
            last: pendingMeta.last_page,
          }) }}
        </span>
        <button
          class="btn-page"
          :disabled="pendingMeta.current_page >= pendingMeta.last_page"
          @click="goPending(pendingMeta.current_page + 1)"
        >
          {{ t('queues.page_next') }} →
        </button>
      </div>
    </section>

    <!-- Recent ------------------------------------------------------- -->
    <section class="card">
      <h2 class="section-title">
        {{ t('queues.section_recent') }}
        <span v-if="recentMeta.total" class="count">{{ recentMeta.total }}</span>
      </h2>
      <div v-if="recent.length === 0" class="empty-state-inline">
        {{ t('queues.recent_empty') }}
      </div>
      <table v-else class="table">
        <thead>
          <tr>
            <th>{{ t('queues.col_job') }}</th>
            <th>{{ t('queues.col_status') }}</th>
            <th class="num">{{ t('queues.col_attempts') }}</th>
            <th>{{ t('queues.col_completed_at') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in recent"
            :key="r.completed_at + r.id"
            class="clickable"
            @click="$router.push({
              name: 'system-queue-job',
              params: { queue, id: r.id },
            })"
          >
            <td>
              <div class="strong mono tiny">{{ r.job_class }}</div>
              <div class="muted tiny">{{ r.id }}</div>
            </td>
            <td>
              <span class="status-pill" :class="`status-${r.status}`">
                {{ t(`queues.status_${r.status}`) }}
              </span>
            </td>
            <td class="num muted">{{ r.attempts }}</td>
            <td class="muted tiny">{{ formatTimestamp(r.completed_at) }}</td>
            <td class="muted">→</td>
          </tr>
        </tbody>
      </table>
      <div v-if="recentMeta.last_page > 1" class="pager">
        <button
          class="btn-page"
          :disabled="recentMeta.current_page <= 1"
          @click="goRecent(recentMeta.current_page - 1)"
        >
          ← {{ t('queues.page_prev') }}
        </button>
        <span class="pager-info">
          {{ t('queues.page_of', {
            current: recentMeta.current_page,
            last: recentMeta.last_page,
          }) }}
        </span>
        <button
          class="btn-page"
          :disabled="recentMeta.current_page >= recentMeta.last_page"
          @click="goRecent(recentMeta.current_page + 1)"
        >
          {{ t('queues.page_next') }} →
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0.25rem 0 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.back-link {
  font-size: 0.8rem;
  color: var(--text-muted);
  text-decoration: none;
}

.back-link:hover {
  color: var(--accent);
}

.driver-line {
  margin-top: 0.25rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.driver-line code {
  background: var(--bg-sidebar);
  padding: 1px 6px;
  border-radius: 4px;
}

.btn-refresh {
  border-radius: 6px;
  border: 1px solid var(--border);
  padding: 0.4rem 0.9rem;
  font-size: 0.85rem;
  cursor: pointer;
  background: none;
  color: var(--text-secondary);
}

.btn-refresh:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--accent);
  border-color: var(--accent);
}

.btn-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.table th {
  text-align: left;
  padding: 0.65rem 1rem;
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--border);
}

.table td {
  padding: 0.65rem 1rem;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  vertical-align: top;
}

.table tr:last-child td {
  border-bottom: none;
}

.clickable {
  cursor: pointer;
  transition: background 0.12s;
}

.clickable:hover {
  background: var(--bg-hover);
}

.num {
  text-align: right;
}

.strong {
  font-weight: 600;
}

.muted {
  color: var(--text-muted);
}

.tiny {
  font-size: 0.75rem;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.85rem;
}

.section-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border);
  background: var(--bg-sidebar);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.card {
  margin-bottom: 1.25rem;
}

.count {
  display: inline-block;
  padding: 0.05rem 0.5rem;
  background: var(--bg-active);
  color: var(--accent);
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
}

.status-pill {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.status-pending {
  background: rgba(56, 139, 253, 0.15);
  color: var(--accent);
}

.status-completed {
  background: rgba(63, 185, 80, 0.15);
  color: #3fb950;
}

.status-failed {
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-danger);
}

.status-cancelled {
  background: rgba(210, 153, 34, 0.15);
  color: #d29922;
}

.loading,
.empty-state,
.empty-state-inline {
  padding: 2rem;
  text-align: center;
  color: var(--text-muted);
}

.empty-state-inline {
  padding: 1.25rem;
  font-size: 0.85rem;
}

.error {
  padding: 0.7rem 1rem;
  background: rgba(239, 68, 68, 0.1);
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 8px;
  font-size: 0.85rem;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 0.65rem 1rem;
  border-top: 1px solid var(--border);
  background: var(--bg-sidebar);
  font-size: 0.8rem;
}

.pager-info {
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.btn-page {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.3rem 0.75rem;
  background: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.8rem;
  transition: background 0.12s, color 0.12s, border-color 0.12s;
}

.btn-page:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--accent);
  border-color: var(--accent);
}

.btn-page:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
