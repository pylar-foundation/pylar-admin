/**
 * Vue-i18n setup for the admin SPA.
 *
 * Catalogues live inline so there is no additional network round-trip
 * on boot. Keys mirror the backend admin.* namespace — but note that
 * the menu labels and the Cron table headers fetched from the API are
 * already translated server-side by pylar.i18n; vue-i18n handles the
 * pieces that live purely on the client (login form, error messages,
 * helpers that format relative time).
 *
 * Active locale is persisted in a ``pylar_admin_locale`` cookie so the
 * API client can echo it as ``Accept-Language`` on every request —
 * that is how the backend picks a locale for the menu endpoint when
 * the browser's own preferences don't point at a supported language.
 */
import { createI18n } from 'vue-i18n'

export const SUPPORTED_LOCALES = ['en', 'ru'] as const
export type Locale = (typeof SUPPORTED_LOCALES)[number]

const messages = {
  en: {
    login: {
      title: 'Sign in',
      email: 'Email',
      password: 'Password',
      submit: 'Sign in',
      submitting: 'Signing in…',
      failed: 'Sign-in failed',
      or: 'Or',
      passkey_submit: 'Sign in with passkey',
      passkey_submitting: 'Waiting for passkey…',
      passkey_cancelled: 'Passkey sign-in was cancelled',
      passkey_failed: 'Passkey sign-in failed',
    },
    cron: {
      title: 'Scheduled tasks',
      refresh: 'Refresh',
      refreshing: 'Refreshing…',
      loading: 'Loading…',
      empty: 'No scheduled tasks registered.',
      col_name: 'Name',
      col_description: 'Description',
      col_cron: 'Cron',
      col_schedule: 'Schedule',
      col_type: 'Type',
      col_timezone: 'Time zone',
      col_next_run: 'Next run',
      due_now: 'due now',
      in_seconds: 'in {n}s',
      in_minutes: 'in {n}m',
      in_minutes_seconds: 'in {m}m {s}s',
      in_hours: 'in {n}h',
      in_days: 'in {n}d',
      every_n_seconds: 'every {n}s',
      every_n_minutes: 'every {n}m',
      every_n_hours: 'every {n}h',
    },
    sidebar: {
      logout: 'Logout',
      language: 'Language',
      profile: 'Profile',
    },
    profile: {
      title: 'Profile',
      subtitle: 'Your account details and security keys',
      load_failed: 'Could not load the profile.',
      field_name: 'Name',
      field_email: 'Email',
      field_id: 'Identifier',
      section_passkeys: 'Passkeys',
      add_passkey: 'Add passkey',
      registering: 'Waiting for authenticator…',
      nickname_prompt: 'Passkey nickname (optional)',
      webauthn_unavailable: 'WebAuthn is not configured for this deployment.',
      passkey_unsupported: 'Your browser does not support WebAuthn passkeys.',
      passkey_registered: 'Passkey added successfully.',
      passkey_revoked: 'Passkey revoked.',
      passkey_cancelled: 'Registration was cancelled.',
      passkey_failed: 'Operation failed.',
      no_passkeys: 'No passkeys registered yet. Add one to sign in without a password.',
      unnamed_passkey: 'Unnamed',
      confirm_revoke: 'Revoke passkey "{label}"? You will need to enrol again to use it.',
      synced: 'Synced across devices',
      col_nickname: 'Nickname',
      col_transports: 'Transports',
      col_created: 'Registered',
      col_last_used: 'Last used',
      rename: 'Rename',
      save: 'Save',
      cancel: 'Cancel',
      revoke: 'Revoke',
    },
    queues: {
      title: 'Queues',
      driver: 'Driver',
      section_queues: 'Named queues',
      section_failed: 'Failed jobs',
      col_name: 'Name',
      col_size: 'Pending',
      col_tries: 'Tries',
      col_workers_live: 'Live',
      col_timeout: 'Timeout',
      col_workers: 'Range',
      col_job: 'Job',
      col_queue: 'Queue',
      col_attempts: 'Attempts',
      col_error: 'Error',
      col_failed_at: 'Failed at',
      col_payload: 'Payload',
      col_queued_at: 'Queued at',
      pending_empty: 'No pending jobs in this queue.',
      purge: 'Purge',
      retry: 'Retry',
      forget: 'Forget',
      cancel: 'Cancel',
      retry_all: 'Retry all',
      flush_all: 'Flush all',
      no_failed: 'No failed jobs.',
      load_failed: 'Failed to load queues',
      retry_failed: 'Retry failed',
      forget_failed: 'Forget failed',
      confirm_forget: 'Forget {job} permanently?',
      confirm_retry_all: 'Re-queue every failed job?',
      confirm_flush_all: 'Drop every failed job? This cannot be undone.',
      confirm_purge: 'Drop every pending job in {queue}?',
      confirm_cancel: 'Cancel this pending job?',
      back_to_queues: 'Queues',
      job_detail: 'Job detail',
      job_id: 'Job id',
      job_status: 'Status',
      status_pending: 'Pending',
      status_failed: 'Failed',
      status_completed: 'Completed',
      status_cancelled: 'Cancelled',
      section_pending: 'Pending',
      section_recent: 'Recent jobs',
      recent_empty: 'No recent jobs (history not stored or window expired).',
      page_prev: 'Prev',
      page_next: 'Next',
      page_of: 'Page {current} of {last}',
      col_status: 'Status',
      col_completed_at: 'Completed at',
      completed_at: 'Completed at',
      available_at: 'Available at',
      payload: 'Payload',
      error_trace: 'Error / traceback',
      output: 'Output',
      output_not_captured: 'Job output is not captured by this driver.',
    },
    webauthn: {
      title: 'Passkeys',
      subtitle: 'Registered WebAuthn credentials',
      unavailable: 'WebAuthn module is not installed. Install pylar[webauthn] to manage passkeys here.',
      no_credentials: 'No passkeys registered yet.',
      load_failed: 'Could not load WebAuthn credentials.',
      revoke_failed: 'Could not revoke this credential.',
      update_failed: 'Could not save the nickname.',
      confirm_revoke: 'Revoke passkey for {label}? The user will need to enrol again.',
      col_user: 'User',
      col_nickname: 'Nickname',
      col_transports: 'Transports',
      col_sign_count: 'Signs',
      col_created: 'Registered',
      col_last_used: 'Last used',
      nickname_placeholder: 'Friendly name',
      no_nickname: 'Unnamed',
      rename: 'Rename',
      save: 'Save',
      cancel: 'Cancel',
      revoke: 'Revoke',
      synced: 'Synced across devices',
    },
  },
  ru: {
    login: {
      title: 'Вход',
      email: 'Email',
      password: 'Пароль',
      submit: 'Войти',
      submitting: 'Входим…',
      failed: 'Ошибка входа',
      or: 'или',
      passkey_submit: 'Войти по passkey',
      passkey_submitting: 'Ожидание passkey…',
      passkey_cancelled: 'Вход по passkey отменён',
      passkey_failed: 'Не удалось войти по passkey',
    },
    cron: {
      title: 'Расписание задач',
      refresh: 'Обновить',
      refreshing: 'Обновление…',
      loading: 'Загрузка…',
      empty: 'Нет зарегистрированных задач.',
      col_name: 'Название',
      col_description: 'Описание',
      col_cron: 'Cron',
      col_schedule: 'Расписание',
      col_type: 'Тип',
      col_timezone: 'Таймзона',
      col_next_run: 'Следующий запуск',
      due_now: 'уже пора',
      in_seconds: 'через {n} с',
      in_minutes: 'через {n} мин',
      in_minutes_seconds: 'через {m} мин {s} с',
      in_hours: 'через {n} ч',
      in_days: 'через {n} дн',
      every_n_seconds: 'каждые {n} с',
      every_n_minutes: 'каждые {n} мин',
      every_n_hours: 'каждые {n} ч',
    },
    sidebar: {
      logout: 'Выйти',
      language: 'Язык',
      profile: 'Профиль',
    },
    profile: {
      title: 'Профиль',
      subtitle: 'Данные учётной записи и ключи безопасности',
      load_failed: 'Не удалось загрузить профиль.',
      field_name: 'Имя',
      field_email: 'Email',
      field_id: 'Идентификатор',
      section_passkeys: 'Passkey',
      add_passkey: 'Добавить passkey',
      registering: 'Ожидание аутентификатора…',
      nickname_prompt: 'Название passkey (необязательно)',
      webauthn_unavailable: 'Модуль WebAuthn не настроен для этого деплоя.',
      passkey_unsupported: 'Браузер не поддерживает WebAuthn passkey.',
      passkey_registered: 'Passkey успешно добавлен.',
      passkey_revoked: 'Passkey отозван.',
      passkey_cancelled: 'Регистрация отменена.',
      passkey_failed: 'Операция не выполнена.',
      no_passkeys: 'Passkey пока не добавлены. Добавьте, чтобы входить без пароля.',
      unnamed_passkey: 'Без названия',
      confirm_revoke: 'Отозвать passkey «{label}»? Для повторного использования нужно будет зарегистрировать заново.',
      synced: 'Синхронизирован между устройствами',
      col_nickname: 'Название',
      col_transports: 'Транспорт',
      col_created: 'Зарегистрирован',
      col_last_used: 'Использован',
      rename: 'Переименовать',
      save: 'Сохранить',
      cancel: 'Отмена',
      revoke: 'Отозвать',
    },
    queues: {
      title: 'Очереди',
      driver: 'Драйвер',
      section_queues: 'Именованные очереди',
      section_failed: 'Сбойные задания',
      col_name: 'Название',
      col_size: 'В очереди',
      col_tries: 'Попыток',
      col_timeout: 'Таймаут',
      col_workers_live: 'Активных',
      col_workers: 'Диапазон',
      col_job: 'Задача',
      col_queue: 'Очередь',
      col_attempts: 'Попыток',
      col_error: 'Ошибка',
      col_failed_at: 'Дата сбоя',
      col_payload: 'Данные',
      col_queued_at: 'Поставлено',
      pending_empty: 'Задач в очереди нет.',
      purge: 'Очистить',
      retry: 'Повторить',
      forget: 'Удалить',
      cancel: 'Отменить',
      retry_all: 'Повторить все',
      flush_all: 'Удалить все',
      no_failed: 'Сбойных заданий нет.',
      load_failed: 'Не удалось загрузить очереди',
      retry_failed: 'Не удалось перепоставить задачу',
      forget_failed: 'Не удалось удалить задачу',
      confirm_forget: 'Удалить {job} без повторной постановки?',
      confirm_retry_all: 'Перепоставить все сбойные задания в очередь?',
      confirm_flush_all: 'Удалить все сбойные задания? Действие необратимо.',
      confirm_purge: 'Удалить все задания из очереди {queue}?',
      confirm_cancel: 'Отменить задачу в очереди?',
      back_to_queues: 'Очереди',
      job_detail: 'Подробности задачи',
      job_id: 'Идентификатор',
      job_status: 'Статус',
      status_pending: 'В очереди',
      status_failed: 'Ошибка',
      status_completed: 'Выполнено',
      status_cancelled: 'Отменено',
      section_pending: 'В очереди',
      section_recent: 'Недавние задачи',
      recent_empty: 'История пуста (драйвер не хранит её или окно истекло).',
      page_prev: 'Назад',
      page_next: 'Вперёд',
      page_of: 'Страница {current} из {last}',
      col_status: 'Статус',
      col_completed_at: 'Завершено',
      completed_at: 'Завершено',
      available_at: 'Доступна с',
      payload: 'Данные',
      error_trace: 'Ошибка / трейс',
      output: 'Вывод',
      output_not_captured: 'Этот драйвер не сохраняет вывод задачи.',
    },
    webauthn: {
      title: 'Passkeys',
      subtitle: 'Зарегистрированные ключи WebAuthn',
      unavailable: 'Модуль WebAuthn не установлен. Поставьте pylar[webauthn], чтобы управлять ключами отсюда.',
      no_credentials: 'Нет зарегистрированных passkey.',
      load_failed: 'Не удалось загрузить список ключей.',
      revoke_failed: 'Не удалось отозвать ключ.',
      update_failed: 'Не удалось сохранить название.',
      confirm_revoke: 'Отозвать passkey для {label}? Пользователю придётся регистрировать заново.',
      col_user: 'Пользователь',
      col_nickname: 'Название',
      col_transports: 'Транспорт',
      col_sign_count: 'Подписей',
      col_created: 'Зарегистрирован',
      col_last_used: 'Использован',
      nickname_placeholder: 'Удобное имя',
      no_nickname: 'Без имени',
      rename: 'Переименовать',
      save: 'Сохранить',
      cancel: 'Отмена',
      revoke: 'Отозвать',
      synced: 'Синхронизирован между устройствами',
    },
  },
}

const COOKIE_KEY = 'pylar_admin_locale'

function readCookieLocale(): Locale | null {
  if (typeof document === 'undefined') return null
  const match = document.cookie.match(/(?:^|;\s*)pylar_admin_locale=([^;]+)/)
  if (!match) return null
  const value = decodeURIComponent(match[1])
  return SUPPORTED_LOCALES.includes(value as Locale) ? (value as Locale) : null
}

function negotiateLocale(): Locale {
  const fromCookie = readCookieLocale()
  if (fromCookie) return fromCookie
  if (typeof navigator === 'undefined') return 'en'
  const prefs = navigator.languages ?? [navigator.language]
  for (const raw of prefs) {
    const short = raw.split('-')[0].toLowerCase()
    if (SUPPORTED_LOCALES.includes(short as Locale)) {
      return short as Locale
    }
  }
  return 'en'
}

export const i18n = createI18n({
  legacy: false,
  locale: negotiateLocale(),
  fallbackLocale: 'en',
  messages,
})

/** Persist *locale* so both the SPA and future API requests pick it up. */
export function setLocale(locale: Locale): void {
  i18n.global.locale.value = locale
  if (typeof document === 'undefined') return
  // Cookie path=/admin so it scopes to the admin surface; one year
  // expiry is plenty for a preference.
  const maxAge = 60 * 60 * 24 * 365
  document.cookie = `${COOKIE_KEY}=${encodeURIComponent(locale)}; path=/admin; max-age=${maxAge}; SameSite=Lax`
}

/** Read the current locale from the cookie, defaulting to 'en'. */
export function currentLocale(): Locale {
  return (i18n.global.locale.value as Locale) || 'en'
}
