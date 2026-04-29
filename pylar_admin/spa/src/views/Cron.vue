<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '@/api/client'

const { t } = useI18n()

interface ScheduleTask {
  name: string | null
  description: string
  cron: string | null
  interval_seconds: number | null
  schedule_kind: 'cron' | 'interval'
  timezone: string
  next_run_at: string | null
  type: string
}

function formatSchedule(task: ScheduleTask): string {
  if (task.schedule_kind === 'interval' && task.interval_seconds !== null) {
    const n = task.interval_seconds
    if (n < 60) return t('cron.every_n_seconds', { n })
    if (n % 3600 === 0) return t('cron.every_n_hours', { n: n / 3600 })
    if (n % 60 === 0) return t('cron.every_n_minutes', { n: n / 60 })
    return t('cron.every_n_seconds', { n })
  }
  return task.cron ?? '—'
}

const tasks = ref<ScheduleTask[]>([])
const loading = ref(true)
const error = ref<string>('')

/**
 * ``nowMs`` drives the live countdown: every second we bump it so
 * every relative time helper below (which reads it reactively) gets
 * re-evaluated and the UI ticks without a full re-fetch.
 * Separately we re-hit ``/system/schedule`` every ``RELOAD_MS`` so
 * ``next_run_at`` picks up whatever the scheduler kernel last ran —
 * interval tasks change that field on every tick, cron tasks only
 * when the minute boundary rolls over.
 */
const nowMs = ref<number>(Date.now())
const RELOAD_MS = 10_000
let tickTimer: ReturnType<typeof setInterval> | undefined
let reloadTimer: ReturnType<typeof setInterval> | undefined

async function load() {
  error.value = ''
  try {
    const res = await api.get<{ tasks: ScheduleTask[] }>('/system/schedule')
    tasks.value = res.tasks
  } catch (e: any) {
    error.value = e.body?.message || t('cron.loading')
  } finally {
    loading.value = false
  }
}

function formatNextRun(iso: string | null): string {
  if (iso === null) return '—'
  const dt = new Date(iso)
  if (Number.isNaN(dt.getTime())) return iso
  return dt.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

/**
 * Live countdown string for *iso*, reactive on ``nowMs``.
 *
 * Template consumers get a fresh value every second because the
 * computed expression reads ``nowMs.value`` — the 1s timer below
 * just mutates that ref and Vue does the rest.
 */
function relativeTo(iso: string | null): string {
  if (iso === null) return ''
  const dt = new Date(iso).getTime()
  if (Number.isNaN(dt)) return ''
  const diff = dt - nowMs.value
  if (diff <= 0) return t('cron.due_now')
  const seconds = Math.round(diff / 1000)
  if (seconds < 60) return t('cron.in_seconds', { n: seconds })
  const minutes = Math.floor(seconds / 60)
  const remSecs = seconds % 60
  if (minutes < 60) {
    // Show "3m 42s" when we still have seconds to render; once we
    // drop below a minute the in_seconds branch takes over.
    if (minutes < 10 && remSecs > 0) {
      return t('cron.in_minutes_seconds', { m: minutes, s: remSecs })
    }
    return t('cron.in_minutes', { n: minutes })
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return t('cron.in_hours', { n: hours })
  const days = Math.round(hours / 24)
  return t('cron.in_days', { n: days })
}

/** True when the computed next-run has already elapsed (scheduler
 *  is running late or the page is stale). */
function isDue(iso: string | null): boolean {
  if (iso === null) return false
  const dt = new Date(iso).getTime()
  if (Number.isNaN(dt)) return false
  return dt - nowMs.value <= 0
}

const hasTasks = computed(() => tasks.value.length > 0)

onMounted(() => {
  load()
  // Cheap 1-second clock tick. requestAnimationFrame would be
  // visually smoother but wastes CPU rendering seconds-resolution
  // strings at 60Hz.
  tickTimer = setInterval(() => {
    nowMs.value = Date.now()
  }, 1_000)
  // Periodic refetch so ``next_run_at`` reflects the scheduler's
  // latest ``_last_run_at`` — especially relevant for sub-minute
  // interval tasks whose next boundary moves on every tick.
  reloadTimer = setInterval(load, RELOAD_MS)
})

onUnmounted(() => {
  if (tickTimer !== undefined) clearInterval(tickTimer)
  if (reloadTimer !== undefined) clearInterval(reloadTimer)
})
</script>

<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">{{ t('cron.title') }}</h1>
      <button class="btn-refresh" @click="load" :disabled="loading">
        {{ loading ? t('cron.refreshing') : t('cron.refresh') }}
      </button>
    </div>

    <div v-if="loading && !hasTasks" class="loading">{{ t('cron.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="!hasTasks" class="empty-state">
      {{ t('cron.empty') }}
    </div>

    <div v-else class="card">
      <table class="table">
        <thead>
          <tr>
            <th>{{ t('cron.col_name') }}</th>
            <th>{{ t('cron.col_description') }}</th>
            <th class="mono">{{ t('cron.col_schedule') }}</th>
            <th>{{ t('cron.col_type') }}</th>
            <th>{{ t('cron.col_timezone') }}</th>
            <th>{{ t('cron.col_next_run') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(task, idx) in tasks" :key="idx">
            <td class="strong">{{ task.name || '—' }}</td>
            <td class="muted">{{ task.description }}</td>
            <td class="mono">
              <span v-if="task.schedule_kind === 'interval'" class="schedule-tag">
                {{ formatSchedule(task) }}
              </span>
              <span v-else>{{ formatSchedule(task) }}</span>
            </td>
            <td>
              <span class="pill" :class="'pill-' + task.type.toLowerCase()">
                {{ task.type }}
              </span>
            </td>
            <td class="muted">{{ task.timezone }}</td>
            <td>
              <div>{{ formatNextRun(task.next_run_at) }}</div>
              <div
                class="tiny countdown"
                :class="isDue(task.next_run_at) ? 'due' : 'muted'"
              >
                {{ relativeTo(task.next_run_at) }}
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.btn-refresh {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.4rem 0.9rem;
  border-radius: 6px;
  font-size: 0.85rem;
}

.btn-refresh:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
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
  padding: 0.75rem 1rem;
  background: var(--bg-sidebar);
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--border);
}

.table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
}

.table tr:last-child td {
  border-bottom: none;
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

.pill {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  background: var(--bg-sidebar);
  color: var(--text-secondary);
}

.pill-commandtask {
  background: rgba(56, 139, 253, 0.12);
  color: var(--accent);
}

.pill-callabletask {
  background: rgba(63, 185, 80, 0.12);
  color: #3fb950;
}

.pill-jobtask {
  background: rgba(210, 153, 34, 0.15);
  color: #d29922;
}

.schedule-tag {
  display: inline-block;
  padding: 0.1rem 0.55rem;
  background: rgba(210, 153, 34, 0.12);
  color: #d29922;
  border-radius: 4px;
  font-size: 0.8rem;
}

.countdown {
  font-variant-numeric: tabular-nums;
  transition: color 0.2s;
}

.countdown.due {
  color: var(--accent);
  font-weight: 600;
}

.loading,
.empty-state {
  color: var(--text-muted);
  padding: 3rem;
  text-align: center;
}

.error {
  padding: 1rem;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.1);
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.empty-state code {
  background: var(--bg-sidebar);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.85rem;
}
</style>
