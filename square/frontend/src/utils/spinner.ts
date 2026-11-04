import { SPINNER_ART } from '../themes/spinnerArt'
import { squareProfile } from '../services/squareConfig'

/** The festival set, nine spinners (the Festivals of the Spinner Sets design): what a square without a choice of its own uses. */
export const SPINNER_VARIANTS = ['ring', 'chakra', 'dhak', 'shankha', 'lantern', 'holi', 'sparkler', 'pongal-pot', 'sunrise'] as const
export type BuiltInSpinner = (typeof SPINNER_VARIANTS)[number]
/** The id of any spinner of themes/spinnerArt.ts: the six occasions of the spinner sets (W18). */
export type SpinnerVariant = string

/** Every spinner a square can keep, 54 in all. Kept equal to the platform's list and the backend's by a test. */
export const ALL_SPINNER_IDS: string[] = SPINNER_ART.map((a) => a.id)
export const isSpinnerId = (v: unknown): v is string => typeof v === 'string' && ALL_SPINNER_IDS.includes(v)

/**
 * The spinner a loading state shows. `kept` is the set the owner chose for the square (theme_overrides.spinners); nothing kept means the nine
 * festival spinners. One is picked from the pool, so a loading state mounted once keeps its spinner while it shows.
 */
export function randomSpinnerVariant(kept: readonly string[] | null | undefined = squareProfile.themeOverrides?.spinners, rnd: () => number = Math.random): SpinnerVariant {
  const own = (kept ?? []).filter(isSpinnerId)
  const pool: readonly string[] = own.length ? own : SPINNER_VARIANTS
  return pool[Math.min(pool.length - 1, Math.floor(rnd() * pool.length))]
}
