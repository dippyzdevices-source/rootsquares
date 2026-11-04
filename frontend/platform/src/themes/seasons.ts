/**
 * What it is:   The rule for "is this seasonal look on today?" (rootsquares W18-R49, docs/plans/themes-starting-looks-plan.md extra 3).
 * What it does: seasonActive(season, day) is true when the day (UTC) is between the season's start and end; a yearly season repeats every year and may cross the new year
 *               (20 Dec to 5 Jan). The backend (theme_overrides.season_active) and the square server (tenancy.season_covers) have the same rule; tests compare the three.
 * How to use:   import { seasonActive } from '@/themes/seasons'; the Seasonal looks panel (features/portal/ThemeSeasonsPanel.vue) marks the season that is on.
 * Run:          from frontend: npm run test:look
 * Read before:  docs/plans/themes-starting-looks-plan.md section 3.
 * Read after:   features/portal/ThemeSeasonsPanel.vue.
 */
export interface SeasonDays { start: string; end: string; yearly: boolean }

/** `day` is a date; its UTC calendar day is what counts (the square server uses UTC too). */
export function seasonActive(season: SeasonDays, day: Date = new Date()): boolean {
  const ymd = day.toISOString().slice(0, 10)
  if (season.yearly) {
    const a = season.start.slice(5)
    const b = season.end.slice(5)
    const t = ymd.slice(5)
    return a <= b ? a <= t && t <= b : t >= a || t <= b
  }
  return season.start <= ymd && ymd <= season.end
}
