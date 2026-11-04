import { useUiStore } from '../stores/ui'

// Locale-aware date and relative-time formatting for the console screens (Intl, no dependency). Follows the language switch.
export function useFormat() {
  const ui = useUiStore()
  const tag = () => (ui.locale === 'no' ? 'nb-NO' : 'en-GB')
  const date = (iso: string | Date, opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' }) => new Intl.DateTimeFormat(tag(), opts).format(new Date(iso))
  const monthYear = (iso: string) => new Intl.DateTimeFormat(tag(), { month: 'short', year: 'numeric' }).format(new Date(iso))
  const ago = (hours: number) => {
    const rtf = new Intl.RelativeTimeFormat(tag(), { numeric: 'auto' })
    if (hours < 1) return rtf.format(-Math.max(1, Math.round(hours * 60)), 'minute')
    if (hours < 24) return rtf.format(-Math.round(hours), 'hour')
    return rtf.format(-Math.round(hours / 24), 'day')
  }
  return { date, monthYear, ago }
}
