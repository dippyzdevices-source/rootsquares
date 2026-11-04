import type { ComposerTranslation } from 'vue-i18n'
import { ProviderError } from '@/services/authProvider'
import { ApiError } from '@/services/platform'

/** Text for an API error: its code when we have a translation, otherwise the generic message. */
export function errorText(t: ComposerTranslation, e: unknown): string {
  if (e instanceof ProviderError) return e.message // the identity provider's own wording (wrong password, email not confirmed, ...)
  const code = e instanceof ApiError ? e.code : 'generic'
  const key = `plat.errors.${code}`
  const s = t(key)
  const text = s === key ? t('plat.errors.generic') : s
  // a refused form says which field and why (the server's own sentence), so "Check the fields" is not a guess (W26-R7)
  const first = e instanceof ApiError && code === 'validation_error' ? e.errors[0] : undefined
  return first?.msg ? `${text} (${first.loc.join('.')}: ${first.msg})` : text
}
