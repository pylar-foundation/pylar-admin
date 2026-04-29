<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api } from '@/api/client'
import CodeBlock from '@/components/CodeBlock.vue'

const props = defineProps<{ queue: string; id: string }>()

const { t } = useI18n()
const router = useRouter()

interface JobDetail {
  id: string
  job_class: string
  queue: string
  attempts: number
  queued_at: string
  available_at: string
  status: 'pending' | 'failed' | 'completed' | 'cancelled'
  payload_preview: string
  error: string | null
  /**
   * Unified terminal timestamp. ``null`` for pending records,
   * otherwise the moment the worker ack'd, the fail() call landed,
   * or the admin cancelled the job. Takes the place of Laravel
   * Horizon's "Completed at" column.
   */
  completed_at: string | null
}

const job = ref<JobDetail | null>(null)
const loading = ref(true)
const error = ref('')
const busy = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get<JobDetail>(
      `/system/queues/${encodeURIComponent(props.queue)}/jobs/${encodeURIComponent(props.id)}`,
    )
    job.value = res
  } catch (e: any) {
    error.value = e.body?.error || e.body?.message || t('queues.load_failed')
    if (e.status === 404) {
      job.value = null
    }
  } finally {
    loading.value = false
  }
}

async function cancel() {
  if (!job.value) return
  if (!confirm(t('queues.confirm_cancel'))) return
  busy.value = true
  try {
    await api.del(
      `/system/queues/${encodeURIComponent(props.queue)}/pending/${encodeURIComponent(props.id)}`,
    )
    router.push({ name: 'system-queue', params: { queue: props.queue } })
  } catch (e: any) {
    error.value = e.body?.message || t('queues.retry_failed')
  } finally {
    busy.value = false
  }
}

async function retry() {
  if (!job.value) return
  busy.value = true
  try {
    await api.post('/system/queues/failed/retry', { id: job.value.id })
    await load()
  } catch (e: any) {
    error.value = e.body?.message || t('queues.retry_failed')
  } finally {
    busy.value = false
  }
}

async function forget() {
  if (!job.value) return
  if (!confirm(t('queues.confirm_forget', { job: job.value.job_class }))) return
  busy.value = true
  try {
    await api.del(`/system/queues/failed/${encodeURIComponent(job.value.id)}`)
    router.push({ name: 'system-queues' })
  } catch (e: any) {
    error.value = e.body?.message || t('queues.forget_failed')
  } finally {
    busy.value = false
  }
}

function formatTimestamp(iso: string | null): string {
  if (iso === null) return '—'
  const dt = new Date(iso)
  return Number.isNaN(dt.getTime())
    ? iso
    : dt.toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      })
}

/**
 * Pretty-print the payload as JSON so highlight.js has structure to
 * highlight; fall back to the raw string when it isn't valid JSON.
 */
const prettyPayload = computed(() => {
  if (!job.value) return ''
  try {
    return JSON.stringify(JSON.parse(job.value.payload_preview), null, 2)
  } catch {
    return job.value.payload_preview
  }
})

const statusClass = computed(() => {
  if (!job.value) return ''
  return `status-${job.value.status}`
})

onMounted(load)
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <router-link
          :to="{ name: 'system-queue', params: { queue } }"
          class="back-link"
        >
          ← {{ queue }}
        </router-link>
        <h1 class="page-title">{{ t('queues.job_detail') }}</h1>
      </div>
      <button class="btn-refresh" @click="load" :disabled="loading">
        {{ loading ? t('cron.refreshing') : t('cron.refresh') }}
      </button>
    </div>

    <div v-if="loading && !job" class="loading">{{ t('cron.loading') }}</div>
    <div v-else-if="error && !job" class="error">{{ error }}</div>

    <template v-else-if="job">
      <div v-if="error" class="error">{{ error }}</div>

      <section class="card">
        <dl class="fields">
          <div class="field">
            <dt>{{ t('queues.col_job') }}</dt>
            <dd class="mono strong">{{ job.job_class }}</dd>
          </div>
          <div class="field">
            <dt>{{ t('queues.job_id') }}</dt>
            <dd class="mono">{{ job.id }}</dd>
          </div>
          <div class="field">
            <dt>{{ t('queues.col_queue') }}</dt>
            <dd class="mono">{{ job.queue }}</dd>
          </div>
          <div class="field">
            <dt>{{ t('queues.job_status') }}</dt>
            <dd>
              <span class="status-pill" :class="statusClass">
                {{ t(`queues.status_${job.status}`) }}
              </span>
            </dd>
          </div>
          <div class="field">
            <dt>{{ t('queues.col_attempts') }}</dt>
            <dd>{{ job.attempts }}</dd>
          </div>
          <div class="field">
            <dt>{{ t('queues.col_queued_at') }}</dt>
            <dd>{{ formatTimestamp(job.queued_at) }}</dd>
          </div>
          <div v-if="job.status === 'pending'" class="field">
            <dt>{{ t('queues.available_at') }}</dt>
            <dd>{{ formatTimestamp(job.available_at) }}</dd>
          </div>
          <div v-else-if="job.completed_at" class="field">
            <dt>{{ t('queues.completed_at') }}</dt>
            <dd>{{ formatTimestamp(job.completed_at) }}</dd>
          </div>
        </dl>

        <div class="actions">
          <button
            v-if="job.status === 'pending'"
            class="btn-danger"
            :disabled="busy"
            @click="cancel"
          >
            {{ t('queues.cancel') }}
          </button>
          <template v-else-if="job.status === 'failed'">
            <button class="btn-primary" :disabled="busy" @click="retry">
              {{ t('queues.retry') }}
            </button>
            <button class="btn-danger" :disabled="busy" @click="forget">
              {{ t('queues.forget') }}
            </button>
          </template>
        </div>
      </section>

      <section class="card">
        <h2 class="section-title">{{ t('queues.payload') }}</h2>
        <CodeBlock :content="prettyPayload" language="json" />
      </section>

      <section v-if="job.error" class="card">
        <h2 class="section-title">{{ t('queues.error_trace') }}</h2>
        <CodeBlock :content="job.error" language="python" />
      </section>

      <section class="card">
        <h2 class="section-title">{{ t('queues.output') }}</h2>
        <div class="output-empty">{{ t('queues.output_not_captured') }}</div>
      </section>
    </template>
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
}

.back-link {
  font-size: 0.8rem;
  color: var(--text-muted);
  text-decoration: none;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.back-link:hover {
  color: var(--accent);
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
  padding: 1rem;
  margin-bottom: 1.25rem;
}

.section-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.75rem;
}

.fields {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem 1.5rem;
  margin: 0 0 1rem;
}

.field {
  min-width: 0;
}

.field dt {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  font-weight: 600;
  margin-bottom: 0.15rem;
}

.field dd {
  margin: 0;
  color: var(--text-primary);
  font-size: 0.9rem;
  word-break: break-word;
}

.strong {
  font-weight: 600;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.85rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border);
}

.status-pill {
  display: inline-block;
  padding: 0.125rem 0.55rem;
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

.status-failed {
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-danger);
}

.status-completed {
  background: rgba(63, 185, 80, 0.15);
  color: #3fb950;
}

.status-cancelled {
  background: rgba(210, 153, 34, 0.15);
  color: #d29922;
}

.output-empty {
  color: var(--text-muted);
  font-size: 0.85rem;
  padding: 0.5rem 0;
  font-style: italic;
}

.loading,
.error {
  padding: 1rem;
  border-radius: 8px;
}

.loading {
  color: var(--text-muted);
  text-align: center;
}

.error {
  background: rgba(239, 68, 68, 0.1);
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.2);
  font-size: 0.85rem;
  margin-bottom: 1rem;
}
</style>
