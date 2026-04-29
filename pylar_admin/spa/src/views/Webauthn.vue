<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '@/api/client'

const { t } = useI18n()

interface WebauthnCredential {
  id: number
  user: string
  tokenable_type: string
  tokenable_id: string
  nickname: string | null
  aaguid: string | null
  transports: string[]
  sign_count: number
  backup_eligible: boolean
  backup_state: boolean
  created_at: string | null
  last_used_at: string | null
}

interface ListResponse {
  credentials: WebauthnCredential[]
  available: boolean
}

const credentials = ref<WebauthnCredential[]>([])
const available = ref(true)
const loading = ref(true)
const error = ref('')
const busyId = ref<number | null>(null)
const editingId = ref<number | null>(null)
const editingNickname = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get<ListResponse>('/system/webauthn')
    credentials.value = res.credentials
    available.value = res.available
  } catch (e: any) {
    error.value = e.body?.message || t('webauthn.load_failed')
  } finally {
    loading.value = false
  }
}

async function revoke(credential: WebauthnCredential) {
  if (!confirm(t('webauthn.confirm_revoke', { label: credential.nickname || credential.user }))) return
  busyId.value = credential.id
  try {
    await api.del(`/system/webauthn/${credential.id}`)
    await load()
  } catch (e: any) {
    error.value = e.body?.message || t('webauthn.revoke_failed')
  } finally {
    busyId.value = null
  }
}

function startEdit(credential: WebauthnCredential) {
  editingId.value = credential.id
  editingNickname.value = credential.nickname ?? ''
}

function cancelEdit() {
  editingId.value = null
  editingNickname.value = ''
}

async function saveNickname(credential: WebauthnCredential) {
  busyId.value = credential.id
  try {
    await api.patch(`/system/webauthn/${credential.id}`, {
      nickname: editingNickname.value.trim() || null,
    })
    editingId.value = null
    editingNickname.value = ''
    await load()
  } catch (e: any) {
    error.value = e.body?.message || t('webauthn.update_failed')
  } finally {
    busyId.value = null
  }
}

function formatTimestamp(iso: string | null): string {
  if (iso === null) return '—'
  const dt = new Date(iso)
  return Number.isNaN(dt.getTime())
    ? iso
    : dt.toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: '2-digit',
        hour: '2-digit', minute: '2-digit',
      })
}

function formatTransports(transports: string[]): string {
  return transports.length > 0 ? transports.join(', ') : '—'
}

const hasCredentials = computed(() => credentials.value.length > 0)

onMounted(load)
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">{{ t('webauthn.title') }}</h1>
        <div class="subtitle">{{ t('webauthn.subtitle') }}</div>
      </div>
      <button class="btn-refresh" @click="load" :disabled="loading">
        {{ loading ? t('cron.refreshing') : t('cron.refresh') }}
      </button>
    </div>

    <div v-if="loading && !credentials.length" class="loading">{{ t('cron.loading') }}</div>
    <div v-if="error" class="error">{{ error }}</div>

    <section v-if="!available" class="card empty-state">
      {{ t('webauthn.unavailable') }}
    </section>

    <section v-else-if="!hasCredentials && !loading" class="card empty-state">
      {{ t('webauthn.no_credentials') }}
    </section>

    <section v-else-if="hasCredentials" class="card">
      <table class="table">
        <thead>
          <tr>
            <th>{{ t('webauthn.col_user') }}</th>
            <th>{{ t('webauthn.col_nickname') }}</th>
            <th>{{ t('webauthn.col_transports') }}</th>
            <th class="num">{{ t('webauthn.col_sign_count') }}</th>
            <th>{{ t('webauthn.col_created') }}</th>
            <th>{{ t('webauthn.col_last_used') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in credentials" :key="c.id">
            <td>
              <div class="strong">{{ c.user }}</div>
              <div class="muted tiny mono">{{ c.tokenable_id }}</div>
            </td>
            <td>
              <template v-if="editingId === c.id">
                <input
                  v-model="editingNickname"
                  class="nickname-input"
                  :placeholder="t('webauthn.nickname_placeholder')"
                  @keydown.enter="saveNickname(c)"
                  @keydown.escape="cancelEdit"
                />
                <div class="inline-actions">
                  <button
                    class="btn-primary btn-sm"
                    :disabled="busyId === c.id"
                    @click="saveNickname(c)"
                  >
                    {{ t('webauthn.save') }}
                  </button>
                  <button class="btn-ghost btn-sm" @click="cancelEdit">
                    {{ t('webauthn.cancel') }}
                  </button>
                </div>
              </template>
              <template v-else>
                <span v-if="c.nickname">{{ c.nickname }}</span>
                <span v-else class="muted italic">{{ t('webauthn.no_nickname') }}</span>
                <button
                  class="btn-link btn-sm"
                  :disabled="busyId === c.id"
                  @click="startEdit(c)"
                >
                  {{ t('webauthn.rename') }}
                </button>
              </template>
              <div v-if="c.backup_state" class="muted tiny">
                {{ t('webauthn.synced') }}
              </div>
            </td>
            <td class="muted tiny">{{ formatTransports(c.transports) }}</td>
            <td class="num muted tiny">{{ c.sign_count }}</td>
            <td class="muted tiny">{{ formatTimestamp(c.created_at) }}</td>
            <td class="muted tiny">{{ formatTimestamp(c.last_used_at) }}</td>
            <td class="actions-cell" @click.stop>
              <button
                class="btn-danger btn-sm"
                :disabled="busyId === c.id"
                @click="revoke(c)"
              >
                {{ t('webauthn.revoke') }}
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

.subtitle {
  margin-top: 0.25rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.btn-refresh,
.btn-primary,
.btn-danger,
.btn-ghost,
.btn-link {
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

.btn-ghost {
  border-color: transparent;
}

.btn-ghost:hover:not(:disabled) {
  background: var(--bg-hover);
}

.btn-link {
  border-color: transparent;
  color: var(--accent);
  padding-left: 0.35rem;
  padding-right: 0.35rem;
}

.btn-link:hover:not(:disabled) {
  text-decoration: underline;
}

.btn-refresh:disabled,
.btn-primary:disabled,
.btn-danger:disabled,
.btn-ghost:disabled,
.btn-link:disabled {
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

.table th.num,
.table td.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
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

.strong {
  font-weight: 600;
}

.muted {
  color: var(--text-muted);
}

.tiny {
  font-size: 0.75rem;
}

.italic {
  font-style: italic;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.75rem;
}

.nickname-input {
  padding: 0.25rem 0.5rem;
  font-size: 0.85rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-hover);
  color: var(--text-primary);
  width: 100%;
  max-width: 240px;
}

.inline-actions {
  display: flex;
  gap: 0.35rem;
  margin-top: 0.35rem;
}

.actions-cell {
  white-space: nowrap;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9rem;
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
