import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { ThemeMode } from '../themes'
import { i18n, type Locale } from '../i18n'

const read = (key: string): string | null => {
  try { return localStorage.getItem(key) } catch { return null }
}
const write = (key: string, value: string) => {
  try { localStorage.setItem(key, value) } catch { /* storage unavailable */ }
}

export const useUiStore = defineStore('ui', () => {
  const stored = read('rs-mode')
  const prefersDark = typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches
  const mode = ref<ThemeMode>(stored === 'dark' || stored === 'light' ? stored : prefersDark ? 'dark' : 'light')
  const locale = ref<Locale>(read('rs-locale') === 'no' ? 'no' : 'en')

  watch(mode, (m) => {
    // Platform UI: design/_ds dark.css is opt-in via data-theme="dark"; light is the default (no attribute).
    if (m === 'dark') document.documentElement.dataset.theme = 'dark'
    else delete document.documentElement.dataset.theme
    write('rs-mode', m)
  }, { immediate: true })

  watch(locale, (l) => {
    i18n.global.locale.value = l
    document.documentElement.lang = l
    write('rs-locale', l)
  }, { immediate: true })

  const toggleMode = () => { mode.value = mode.value === 'dark' ? 'light' : 'dark' }
  const setLocale = (l: Locale) => { locale.value = l }

  return { mode, locale, toggleMode, setLocale }
})
