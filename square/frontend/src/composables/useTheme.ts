import { ref } from 'vue'
import { activeLayout, opensDark } from '../layout-themes/layouts'
import { squareProfile } from '../services/squareConfig'
import { feelMode, type FeelChoice } from '../themes/feel'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'bca-theme'
const VALID_THEMES: Theme[] = ['light', 'dark']

const theme = ref<Theme>('light')

function applyTheme(value: Theme) {
  document.documentElement.classList.toggle('dark', value === 'dark')
}

function storedTheme(): Theme | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw && (VALID_THEMES as string[]).includes(raw)) return raw as Theme
  } catch {
    // Private browsing / storage disabled — fall back to the default.
  }
  return null
}

function readStoredTheme(feel?: FeelChoice | null): Theme {
  const stored = storedTheme()
  // The owner's default (Feel tab, W18-R44): light, dark or the device setting; the visitor's own choice wins unless the owner hid the switch.
  const owner = feelMode(feel ?? squareProfile.themeOverrides?.feel, stored, !!window.matchMedia?.('(prefers-color-scheme: dark)').matches)
  if (owner) return owner
  if (stored) return stored
  // The original look deliberately has no OS-preference hook — its default ground is paper (light); dark is opt-in only. A square on a layout theme
  // (W9-R5) follows the visitor's system setting until they choose.
  if (opensDark(squareProfile.themeId)) return 'dark' // a theme designed dark opens dark (W9-R10)
  if (activeLayout && window.matchMedia?.('(prefers-color-scheme: dark)').matches) return 'dark'
  return 'light'
}

function setTheme(value: Theme) {
  theme.value = value
  try {
    localStorage.setItem(STORAGE_KEY, value)
  } catch {
    // Private browsing / storage disabled — the choice just won't persist.
  }
  applyTheme(value)
}

function initTheme(feel?: FeelChoice | null) {
  const stored = readStoredTheme(feel)
  theme.value = stored
  applyTheme(stored)
}

export function useTheme() {
  return { theme, setTheme, initTheme }
}
