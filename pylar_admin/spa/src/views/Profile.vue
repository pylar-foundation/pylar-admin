<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '@/api/client'

const { t } = useI18n()

interface UserInfo {
  id: string | number
  email?: string
  username?: string
  name?: string
}

interface Credential {
  id: number
  nickname: string | null
  aaguid: string | null
  transports: string[]
  sign_count: number
  backup_eligible: boolean
  backup_state: boolean
  created_at: string | null
  last_used_at: string | null
}

interface ProfileResponse {
  user: UserInfo
  webauthn_available: boolean
  credentials: Credential[]
}

const user = ref<UserInfo | null>(null)
const webauthnAvailable = ref(false)
const credentials = ref<Credential[]>([])
const loading = ref(true)
const error = ref('')
const notice = ref('')
const busyId = ref<number | null>(null)
const registering = ref(false)
const editingId = ref<number | null>(null)
const editingNickname = ref('')

/**
 * `credentials.get()` / `credentials.create()` travel in ArrayBuffers
 * but our transport is JSON. These helpers translate in both
 * directions using the base64url alphabet WebAuthn mandates.
 */
function b64urlToBuf(value: string): ArrayBuffer {
  const pad = '='.repeat((4 - (value.length % 4)) % 4)
  const b64 = (value + pad).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(b64)
  const buf = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i)
  return buf.buffer
}

function bufToB64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let bin = ''
  for (const b of bytes) bin += String.fromCharCode(b)
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get<ProfileResponse>('/profile')
    user.value = res.user
    webauthnAvailable.value = res.webauthn_available
    credentials.value = res.credentials
  } catch (e: any) {
    error.value = e.body?.message || t('profile.load_failed')
  } finally {
    loading.value = false
  }
}

const platformSupported = computed(
  () => typeof window !== 'undefined' && 'PublicKeyCredential' in window,
)

async function addPasskey() {
  if (!platformSupported.value) {
    error.value = t('profile.passkey_unsupported')
    return
  }
  error.value = ''
  notice.value = ''

  const nickname =
    typeof window !== 'undefined'
      ? window.prompt(t('profile.nickname_prompt'), '')
      : ''

  registering.value = true
  try {
    const options: any = await api.get('/profile/webauthn/register/options')

    const publicKey: PublicKeyCredentialCreationOptions = {
      ...options,
      challenge: b64urlToBuf(options.challenge),
      user: {
        ...options.user,
        id: b64urlToBuf(options.user.id),
      },
      excludeCredentials: (options.excludeCredentials || []).map((c: any) => ({
        ...c,
        id: b64urlToBuf(c.id),
      })),
    }

    const credential = (await navigator.credentials.create({
      publicKey,
    })) as PublicKeyCredential | null
    if (credential === null) {
      throw new Error(t('profile.passkey_cancelled'))
    }
    const attestation = credential.response as AuthenticatorAttestationResponse

    const payload = {
      credential: {
        id: credential.id,
        rawId: bufToB64url(credential.rawId),
        type: credential.type,
        response: {
          attestationObject: bufToB64url(attestation.attestationObject),
          clientDataJSON: bufToB64url(attestation.clientDataJSON),
          transports:
            typeof attestation.getTransports === 'function'
              ? attestation.getTransports()
              : [],
        },
        clientExtensionResults: credential.getClientExtensionResults(),
      },
      nickname: nickname?.trim() || null,
    }

    await api.post('/profile/webauthn/register/verify', payload)
    notice.value = t('profile.passkey_registered')
    await load()
  } catch (e: any) {
    error.value = e.body?.message || e.message || t('profile.passkey_failed')
  } finally {
    registering.value = false
  }
}

function startEdit(credential: Credential) {
  editingId.value = credential.id
  editingNickname.value = credential.nickname ?? ''
}

function cancelEdit() {
  editingId.value = null
  editingNickname.value = ''
}

async function saveNickname(credential: Credential) {
  busyId.value = credential.id
  try {
    await api.patch(`/profile/webauthn/${credential.id}`, {
      nickname: editingNickname.value.trim() || null,
    })
    editingId.value = null
    editingNickname.value = ''
    await load()
  } catch (e: any) {
    error.value = e.body?.message || t('profile.passkey_failed')
  } finally {
    busyId.value = null
  }
}

async function revoke(credential: Credential) {
  const label = credential.nickname || t('profile.unnamed_passkey')
  if (!confirm(t('profile.confirm_revoke', { label }))) return
  busyId.value = credential.id
  try {
    await api.del(`/profile/webauthn/${credential.id}`)
    notice.value = t('profile.passkey_revoked')
    await load()
  } catch (e: any) {
    error.value = e.body?.message || t('profile.passkey_failed')
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

function displayName(u: UserInfo): string {
  return u.name || u.username || u.email || String(u.id)
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">{{ t('profile.title') }}</h1>
        <div class="subtitle">{{ t('profile.subtitle') }}</div>
      </div>
      <button class="btn-refresh" @click="load" :disabled="loading">
        {{ loading ? t('cron.refreshing') : t('cron.refresh') }}
      </button>
    </div>

    <div v-if="loading && !user" class="loading">{{ t('cron.loading') }}</div>
    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="notice" class="notice">{{ notice }}</div>

    <section v-if="user" class="card info-card">
      <div class="info-row">
        <div class="info-label">{{ t('profile.field_name') }}</div>
        <div class="info-value strong">{{ displayName(user) }}</div>
      </div>
      <div v-if="user.email" class="info-row">
        <div class="info-label">{{ t('profile.field_email') }}</div>
        <div class="info-value">{{ user.email }}</div>
      </div>
      <div class="info-row">
        <div class="info-label">{{ t('profile.field_id') }}</div>
        <div class="info-value mono tiny">{{ user.id }}</div>
      </div>
    </section>

    <section v-if="user" class="card">
      <div class="section-header">
        <h2 class="section-title">{{ t('profile.section_passkeys') }}</h2>
        <div class="section-actions">
          <button
            v-if="webauthnAvailable && platformSupported"
            class="btn-primary"
            :disabled="registering"
            @click="addPasskey"
          >
            <span aria-hidden="true">🔑</span>
            {{ registering ? t('profile.registering') : t('profile.add_passkey') }}
          </button>
        </div>
      </div>

      <div v-if="!webauthnAvailable" class="empty-state">
        {{ t('profile.webauthn_unavailable') }}
      </div>
      <div v-else-if="!platformSupported" class="empty-state">
        {{ t('profile.passkey_unsupported') }}
      </div>
      <div v-else-if="credentials.length === 0" class="empty-state">
        {{ t('profile.no_passkeys') }}
      </div>
      <table v-else class="table">
        <thead>
          <tr>
            <th>{{ t('profile.col_nickname') }}</th>
            <th>{{ t('profile.col_transports') }}</th>
            <th>{{ t('profile.col_created') }}</th>
            <th>{{ t('profile.col_last_used') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in credentials" :key="c.id">
            <td>
              <template v-if="editingId === c.id">
                <input
                  v-model="editingNickname"
                  class="nickname-input"
                  :placeholder="t('profile.nickname_prompt')"
                  @keydown.enter="saveNickname(c)"
                  @keydown.escape="cancelEdit"
                />
                <div class="inline-actions">
                  <button class="btn-primary btn-sm" :disabled="busyId === c.id" @click="saveNickname(c)">
                    {{ t('profile.save') }}
                  </button>
                  <button class="btn-ghost btn-sm" @click="cancelEdit">
                    {{ t('profile.cancel') }}
                  </button>
                </div>
              </template>
              <template v-else>
                <span v-if="c.nickname" class="strong">{{ c.nickname }}</span>
                <span v-else class="muted italic">{{ t('profile.unnamed_passkey') }}</span>
                <button class="btn-link btn-sm" :disabled="busyId === c.id" @click="startEdit(c)">
                  {{ t('profile.rename') }}
                </button>
                <div v-if="c.backup_state" class="muted tiny">
                  {{ t('profile.synced') }}
                </div>
              </template>
            </td>
            <td class="muted tiny">{{ formatTransports(c.transports) }}</td>
            <td class="muted tiny">{{ formatTimestamp(c.created_at) }}</td>
            <td class="muted tiny">{{ formatTimestamp(c.last_used_at) }}</td>
            <td class="actions-cell">
              <button
                class="btn-danger btn-sm"
                :disabled="busyId === c.id"
                @click="revoke(c)"
              >
                {{ t('profile.revoke') }}
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

.btn-primary:hover:not(:disabled),
.btn-refresh:hover:not(:disabled) {
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

.btn-primary:disabled,
.btn-danger:disabled,
.btn-refresh:disabled,
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
  margin-bottom: 1.25rem;
}

.info-card {
  padding: 1.25rem;
}

.info-row {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 1rem;
  padding: 0.45rem 0;
  font-size: 0.9rem;
}

.info-row + .info-row {
  border-top: 1px solid var(--border);
}

.info-label {
  color: var(--text-muted);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  align-self: center;
}

.info-value {
  color: var(--text-primary);
  word-break: break-word;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border);
  background: var(--bg-sidebar);
}

.section-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.section-actions {
  display: flex;
  gap: 0.5rem;
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

.error,
.notice {
  margin: 0 0 1rem;
  padding: 0.7rem 1rem;
  border-radius: 8px;
  font-size: 0.85rem;
}

.error {
  background: rgba(239, 68, 68, 0.1);
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.notice {
  background: rgba(63, 185, 80, 0.12);
  color: #3fb950;
  border: 1px solid rgba(63, 185, 80, 0.25);
}
</style>
