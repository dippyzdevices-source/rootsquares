// Gated features of a module that only some launch packages include (W14-R25, docs/reference/packages-and-features.md; the server is square/backend/app/features.py).
// A locked feature stays visible with one line saying which package includes it; nothing is hidden or deleted.
import { squareProfile } from './squareConfig'

export type FeatureKey = 'message_reminders' | 'repeating_events'

export function featureEnabled(key: FeatureKey): boolean {
  return squareProfile.features.includes(key)
}

/** The one line a locked feature shows. */
export const GROVE_NOTE = 'Included in the Grove package.'
