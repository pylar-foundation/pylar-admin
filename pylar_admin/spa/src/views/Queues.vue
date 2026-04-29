<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '@/api/client'

const { t } = useI18n()

interface QueuePolicy {
  tries: number | null
  timeout: number | null
  backoff: number[]
  min_workers: number | null
  max_workers: number | null
}

interface QueueSummary {
  name: string
  size: number
  workers: number
  policy: QueuePolicy
}

interface FailedRecord {
  id: string
  job_class: string
  queue: string
  attempts: number
  queued_at: string
  available_at: string
  error: string
  failed_at: string
}

interface QueuesResponse {
  queues: QueueSummary[]
  failed_count: number
  driver: string | null
}

interface FailedResponse {
  records: FailedRecord[]
  driver: string | null
}

const summary = ref<QueuesResponse | null>(null)
const failed = ref<FailedRecord[]>([])
const loading = ref(true)
const error = ref('')
const busyId = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [s, f] = await Promise.all([
      api.get<QueuesResponse>('/system/queues'),
      api.get<FailedResponse>('/system/queues/failed'),
    ])
    summary.value = s
    failed.value = f.records
  } catch (e: any) {
    error.value = e.body?.message || t('queues.load_failed')
  } finally {
    loading.value = false
  }
}

async function retryOne(record: FailedRecord) {
  busyId.value = record.id
  try {
    await api.post('/system/queues/failed/retry', { id: record.id })
    await load()
  } catch (e: any) {
    error.value = e.body?.message || t('queues.retry_failed')
  } finally {
    busyId.value = null
  }
}

async function forgetOne(record: FailedRecord) {
  if (!confirm(t('queues.confirm_forget', { job: record.job_class }))) return
  busyId.value = record.id
  try {
    await api.del(`/system/queues/failed/${encodeURIComponent(record.id)}`)
    await load()
  } catch (e: any) {
    error.value = e.body?.message || t('queues.forget_failed')
  } finally {
    busyId.value = null
  }
}

async function retryAll() {
  if (failed.value.length === 0) return
  if (!confirm(t('queues.confirm_retry_all'))) return
  busyId.value = '*'
  try {
    await api.post('/system/queues/failed/retry', {})
    await load()
  } finally {
    busyId.value = null
  }
}

async function flushAll() {
  if (failed.value.length === 0) return
  if (!confirm(t('queues.confirm_flush_all'))) return
  busyId.value = '*'
  try {
    await api.del('/system/queues/failed')
    await load()
  } finally {
    busyId.value = null
  }
}

async function purgeQueue(name: string) {
  if (!confirm(t('queues.confirm_purge', { queue: name }))) return
  busyId.value = name
  try {
    await api.post(`/system/queues/${encodeURIComponent(name)}/purge`, {})
    await load()
  } finally {
    busyId.value = null
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

const driverLabel = computed(() => summary.value?.driver ?? '—')
const hasFailed = computed(() => failed.value.length > 0)

onMounted(load)
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">{{ t('queues.title') }}</h1>
        <div class="driver-line">
          {{ t('queues.driver') }}: <code>{{ driverLabel }}</code>
        </div>
      </div>
      <button class="btn-refresh" @click="load" :disabled="loading">
        {{ loading ? t('cron.refreshing') : t('cron.refresh') }}
      </button>
    </div>

    <div v-if="loading && !summary" class="loading">{{ t('cron.loading') }}</div>
    <div v-if="error" class="error">{{ error }}</div>

    <!-- Queues summary -->
    <section v-if="summary" class="card">
      <h2 class="section-title">{{ t('queues.section_queues') }}</h2>
      <table class="table">
        <thead>
          <tr>
            <th>{{ t('queues.col_name') }}</th>
            <th class="num">{{ t('queues.col_size') }}</th>
            <th class="num">{{ t('queues.col_tries') }}</th>
            <th class="num">{{ t('queues.col_timeout') }}</th>
            <th class="num">{{ t('queues.col_workers_live') }}</th>
            <th class="num">{{ t('queues.col_workers') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="q in summary.queues"
            :key="q.name"
            class="clickable"
            @click="$router.push({ name: 'system-queue', params: { queue: q.name } })"
          >
            <td class="strong mono">{{ q.name }}</td>
            <td class="num">
              <span class="pill" :class="{ 'pill-active': q.size > 0 }">
                {{ q.size }}
              </span>
            </td>
            <td class="num muted">{{ q.policy.tries ?? '—' }}</td>
            <td class="num muted">{{ q.policy.timeout ?? '—' }}s</td>
            <td class="num">
              <span class="pill" :class="{ 'pill-active': q.workers > 0 }">
                {{ q.workers }}
              </span>
            </td>
            <td class="num muted">
              {{ q.policy.min_workers ?? '—' }} – {{ q.policy.max_workers ?? '—' }}
            </td>
            <td @click.stop>
              <button
                class="btn-danger btn-sm"
                :disabled="q.size === 0 || busyId === q.name"
                @click="purgeQueue(q.name)"
              >
                {{ t('queues.purge') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Failed pool -->
    <section class="card">
      <div class="section-header">
        <h2 class="section-title">
          {{ t('queues.section_failed') }}
          <span v-if="hasFailed" class="count">{{ failed.length }}</span>
        </h2>
        <div class="section-actions">
          <button
            class="btn-primary"
            :disabled="!hasFailed || busyId === '*'"
            @click="retryAll"
          >
            {{ t('queues.retry_all') }}
          </button>
          <button
            class="btn-danger"
            :disabled="!hasFailed || busyId === '*'"
            @click="flushAll"
          >
            {{ t('queues.flush_all') }}
          </button>
        </div>
      </div>

      <div v-if="!hasFailed" class="empty-state">
        {{ t('queues.no_failed') }}
      </div>

      <table v-else class="table">
        <thead>
          <tr>
            <th>{{ t('queues.col_job') }}</th>
            <th>{{ t('queues.col_queue') }}</th>
            <th class="num">{{ t('queues.col_attempts') }}</th>
            <th>{{ t('queues.col_error') }}</th>
            <th>{{ t('queues.col_failed_at') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in failed"
            :key="r.id"
            class="clickable"
            @click="$router.push({
              name: 'system-queue-job',
              params: { queue: r.queue, id: r.id },
            })"
          >
            <td>
              <div class="strong mono tiny">{{ r.job_class }}</div>
              <div class="muted tiny">{{ r.id }}</div>
            </td>
            <td class="mono">{{ r.queue }}</td>
            <td class="num muted">{{ r.attempts }}</td>
            <td class="error-cell">{{ r.error }}</td>
            <td class="muted tiny">{{ formatTimestamp(r.failed_at) }}</td>
            <td class="actions-cell" @click.stop>
              <button
                class="btn-primary btn-sm"
                :disabled="busyId === r.id"
                @click="retryOne(r)"
              >
                {{ t('queues.retry') }}
              </button>
              <button
                class="btn-danger btn-sm"
                :disabled="busyId === r.id"
                @click="forgetOne(r)"
              >
                {{ t('queues.forget') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
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
  margin: 0;
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

.btn-refresh,
.btn-primary,
.btn-danger {
  border-radius: 6px;
  border: 1px solid var(--border);
  padding: 0.4rem 0.9rem;
  font-size: 0.85rem;
  cursor: pointer;
  background: none;
  color: var(--text-secondary);
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}

.btn-sm {
  padding: 0.25rem 0.6rem;
  font-size: 0.75rem;
}

.btn-refresh:hover:not(:disabled),
.btn-primary:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--accent);
  border-color: var(--accent);
}

.btn-danger:hover:not(:disabled) {
  background: var(--color-danger);
  color: white;
  border-color: var(--color-danger);
}

.btn-refresh:disabled,
.btn-primary:disabled,
.btn-danger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 1.25rem;
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

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border);
  background: var(--bg-sidebar);
  padding: 0 1rem;
}

.section-header .section-title {
  border-bottom: none;
  padding: 0.75rem 0;
  background: none;
}

.section-actions {
  display: flex;
  gap: 0.5rem;
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

/* The `.table th { text-align: left }` rule below has higher
 * specificity than a bare `.num`, so numeric headers were
 * inheriting the left alignment — qualify the selector to win
 * the cascade. */
.table th.num,
.table td.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  padding-right: 1.25rem;
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

.error-cell {
  max-width: 320px;
  word-break: break-word;
  color: var(--color-danger);
  font-size: 0.8rem;
}

.clickable {
  cursor: pointer;
  transition: background 0.12s;
}

.clickable:hover {
  background: var(--bg-hover);
}

.actions-cell {
  white-space: nowrap;
  display: flex;
  gap: 0.35rem;
}

.pill {
  display: inline-block;
  padding: 0.125rem 0.55rem;
  border-radius: 999px;
  font-weight: 700;
  background: var(--bg-sidebar);
  color: var(--text-secondary);
  min-width: 2rem;
  text-align: center;
}

.pill-active {
  background: rgba(56, 139, 253, 0.15);
  color: var(--accent);
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: var(--text-muted);
}

.loading {
  padding: 2rem;
  text-align: center;
  color: var(--text-muted);
}

.error {
  margin: 0 0 1rem;
  padding: 0.7rem 1rem;
  background: rgba(239, 68, 68, 0.1);
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 8px;
  font-size: 0.85rem;
}
</style>
