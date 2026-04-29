<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api } from '@/api/client'
import { useAdminStore } from '@/stores/admin'

const router = useRouter()
const store = useAdminStore()
const { t } = useI18n()

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

/**
 * Passkey availability is computed once on mount via two signals:
 *
 *  * Browser support: `window.PublicKeyCredential` must exist.
 *  * Server support: a HEAD probe to the options endpoint — any 2xx
 *    means the `WebauthnServer` is bound. A 404 means the extras
 *    aren't installed and we hide the button.
 */
const passkeysAvailable = ref(false)
const passkeyLoading = ref(false)

onMounted(async () => {
  if (typeof window === 'undefined' || !('PublicKeyCredential' in window)) {
    return
  }
  try {
    // GET is cheap and the endpoint is idempotent (issues a fresh
    // challenge we discard if the user skips the passkey flow).
    await api.get('/login/webauthn/options')
    passkeysAvailable.value = true
  } catch {
    passkeysAvailable.value = false
  }
})

async function onSubmit() {
  error.value = ''
  loading.value = true

  try {
    const res = await api.post<{ user: any }>('/login', {
      email: email.value,
      password: password.value,
    })
    store.setUser(res.user)
    router.push({ name: 'dashboard' })
  } catch (e: any) {
    error.value = e.body?.message || t('login.failed')
  } finally {
    loading.value = false
  }
}

/**
 * Convert the server's base64url WebAuthn fields into the ArrayBuffer
 * shape `navigator.credentials.get()` expects, and the opposite on
 * the response side. WebAuthn only travels as ArrayBuffers across
 * the JS API but our transport is JSON.
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

async function onPasskey() {
  error.value = ''
  passkeyLoading.value = true
  try {
    const options: any = await api.get('/login/webauthn/options')

    const publicKey: PublicKeyCredentialRequestOptions = {
      ...options,
      challenge: b64urlToBuf(options.challenge),
      allowCredentials: (options.allowCredentials || []).map((c: any) => ({
        ...c,
        id: b64urlToBuf(c.id),
      })),
    }

    const credential = (await navigator.credentials.get({
      publicKey,
    })) as PublicKeyCredential | null
    if (credential === null) {
      throw new Error(t('login.passkey_cancelled'))
    }

    const assertion = credential.response as AuthenticatorAssertionResponse
    const payload = {
      id: credential.id,
      rawId: bufToB64url(credential.rawId),
      type: credential.type,
      response: {
        authenticatorData: bufToB64url(assertion.authenticatorData),
        clientDataJSON: bufToB64url(assertion.clientDataJSON),
        signature: bufToB64url(assertion.signature),
        userHandle: assertion.userHandle
          ? bufToB64url(assertion.userHandle)
          : null,
      },
      clientExtensionResults: credential.getClientExtensionResults(),
    }

    const res = await api.post<{ user: any }>('/login/webauthn/verify', payload)
    store.setUser(res.user)
    router.push({ name: 'dashboard' })
  } catch (e: any) {
    error.value = e.body?.message || e.message || t('login.passkey_failed')
  } finally {
    passkeyLoading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <svg width="40" height="40" viewBox="0 0 28 28" fill="none">
          <rect width="28" height="28" rx="6" fill="var(--accent)" />
          <text x="7" y="20" fill="white" font-size="16" font-weight="bold">P</text>
        </svg>
        <h1>Pylar Admin</h1>
      </div>

      <form @submit.prevent="onSubmit" class="login-form">
        <div v-if="error" class="login-error">{{ error }}</div>

        <div class="form-group">
          <label for="email">{{ t('login.email') }}</label>
          <input
            id="email"
            v-model="email"
            type="email"
            placeholder="admin@example.com"
            required
            autofocus
            class="form-control"
          />
        </div>

        <div class="form-group">
          <label for="password">{{ t('login.password') }}</label>
          <input
            id="password"
            v-model="password"
            type="password"
            :placeholder="t('login.password')"
            required
            class="form-control"
          />
        </div>

        <button type="submit" class="btn btn-primary btn-block" :disabled="loading">
          {{ loading ? t('login.submitting') : t('login.submit') }}
        </button>
      </form>

      <div v-if="passkeysAvailable" class="passkey-section">
        <div class="divider"><span>{{ t('login.or') }}</span></div>
        <button
          type="button"
          class="btn btn-ghost btn-block passkey-button"
          :disabled="passkeyLoading"
          @click="onPasskey"
        >
          <span class="passkey-icon" aria-hidden="true">🔑</span>
          {{ passkeyLoading ? t('login.passkey_submitting') : t('login.passkey_submit') }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: var(--bg-primary);
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 2.5rem;
}

.login-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 2rem;
}

.login-header h1 {
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--text-primary);
}

.login-form .form-group {
  margin-bottom: 1.25rem;
}

.login-form label {
  display: block;
  margin-bottom: 0.35rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.login-form .form-control {
  width: 100%;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 0.9rem;
}

.login-form .form-control:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-alpha);
}

.btn-block {
  width: 100%;
  justify-content: center;
  padding: 0.65rem;
  font-size: 0.9rem;
}

.login-error {
  background: rgba(239, 68, 68, 0.1);
  color: var(--color-danger);
  padding: 0.6rem 0.75rem;
  border-radius: 6px;
  font-size: 0.85rem;
  margin-bottom: 1rem;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.passkey-section {
  margin-top: 1.5rem;
}

.divider {
  position: relative;
  text-align: center;
  margin: 1rem 0;
  color: var(--text-muted);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.divider::before,
.divider::after {
  content: '';
  position: absolute;
  top: 50%;
  width: calc(50% - 1.5rem);
  height: 1px;
  background: var(--border);
}

.divider::before { left: 0; }
.divider::after  { right: 0; }

.divider span {
  background: var(--bg-card);
  padding: 0 0.5rem;
  position: relative;
}

.passkey-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  font-weight: 500;
  background: none;
  color: var(--text-primary);
  border: 1px solid var(--border);
  padding: 0.55rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: border-color 0.15s, background 0.15s;
}

.passkey-button:hover:not(:disabled) {
  background: var(--bg-hover);
  border-color: var(--accent);
}

.passkey-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.passkey-icon {
  font-size: 1rem;
}
</style>
