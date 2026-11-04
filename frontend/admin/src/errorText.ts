import type { ComposerTranslation } from 'vue-i18n'
import { ApiError } from '@rootsquares/ui/types/platformTypes'

/** Text for an API error in the admin application: its own wording first, then the shared one, then the generic message. */
export function errorText(t: ComposerTranslation, e: unknown): string {
  const code = e instanceof ApiError ? e.code : 'generic'
  for (const key of [`adm.errors.${code}`, `plat.errors.${code}`]) {
    const s = t(key)
    if (s !== key) return s
  }
  return t('plat.errors.generic')
}
