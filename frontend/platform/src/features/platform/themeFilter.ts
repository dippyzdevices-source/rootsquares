import { computed, ref } from 'vue'
import { COMING_THEMES, THEMES, type ThemeDef } from '@rootsquares/ui/themes'

// Search and shell filter of the theme pickers (wizard, a square's Theme page, the public Templates page; W9-R10). The 56 themes are filtered by a
// word (name, colours, who it suits, how it is laid out, fonts) and by how the site is navigated.
export const SHELL_FILTERS: { id: string; label: string }[] = [
  { id: '', label: 'All' },
  { id: 'side', label: 'Left sidebar' },
  { id: 'right', label: 'Right sidebar' },
  { id: 'mast', label: 'Top masthead' },
  { id: 'bar', label: 'Top bar' },
  { id: 'tabs', label: 'Two-row tabs' },
  { id: 'dock', label: 'Bottom dock' },
  { id: 'ref', label: 'Reference layouts' },
]

const haystack = (th: ThemeDef) => [th.name, th.colour, th.suits, th.look, th.shellLabel, th.display, th.body, ...th.kits].join(' ').toLowerCase()

/** Which shell filter a theme belongs to: its own shell, or 'ref' for the sixteen custom reference layouts (which are also listed under their shell). */
export const inShell = (th: ThemeDef, shell: string) => !shell || (shell === 'ref' ? th.kind === 'ref' : th.shell === shell)

export function useThemeFilter(list: ThemeDef[] = THEMES, upcoming: ThemeDef[] = COMING_THEMES) {
  const q = ref('')
  const shell = ref('')
  const words = computed(() => q.value.toLowerCase().split(/\s+/).filter(Boolean))
  const filtered = computed(() => list.filter((th) => inShell(th, shell.value) && words.value.every((w) => haystack(th).includes(w))))
  const counts = computed(() => Object.fromEntries(SHELL_FILTERS.map((f) => [f.id, list.filter((th) => inShell(th, f.id)).length])))
  /** The themes that are built but not offered yet (W10-R8), with the same search and shell filter. */
  const coming = computed(() => upcoming.filter((th) => inShell(th, shell.value) && words.value.every((w) => haystack(th).includes(w))))
  return { q, shell, filtered, counts, coming }
}
