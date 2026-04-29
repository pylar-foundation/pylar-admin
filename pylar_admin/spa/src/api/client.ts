/**
 * Thin HTTP client for the admin JSON API.
 *
 * All paths are relative to the admin API prefix (e.g. /admin/api).
 * Responses are parsed as JSON automatically. 401 responses trigger
 * a redirect to the login page.
 */

const BASE = '/admin/api'

interface ApiError {
  status: number
  body: unknown
}

function getCsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)pylar_csrf=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

function getLocaleCookie(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)pylar_admin_locale=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const csrf = getCsrfToken()
  if (csrf) {
    headers['X-CSRF-Token'] = csrf
  }
  // Echo the chosen admin locale as Accept-Language so the backend's
  // AcceptLanguageMiddleware translates menu labels and other
  // server-rendered strings to match the SPA's UI language.
  const locale = getLocaleCookie()
  if (locale) {
    headers['Accept-Language'] = locale
  }
  const opts: RequestInit = {
    method,
    headers,
  }
  if (body !== undefined) {
    opts.body = JSON.stringify(body)
  }

  const res = await fetch(`${BASE}${path}`, opts)
  const data = await res.json()

  if (!res.ok) {
    // Redirect to login on 401 (unless we're already on the login/user check).
    if (res.status === 401 && !path.startsWith('/login') && !path.startsWith('/user')) {
      window.location.href = '/admin/login'
    }
    const err: ApiError = { status: res.status, body: data }
    throw err
  }

  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
}
