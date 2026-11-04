import { computed, inject, type ComputedRef, type InjectionKey } from 'vue'
import { DEFAULT_TENANT_THEME, getTheme, type ThemeDef } from '@rootsquares/ui/themes'

export const THEME_LAYOUT_KEY: InjectionKey<ComputedRef<ThemeDef>> = Symbol('theme-layout')

// Layout flags (header / hero / event list / image shape) of the nearest ThemeScope.
export function useThemeLayout() {
  return inject(THEME_LAYOUT_KEY, computed(() => getTheme(DEFAULT_TENANT_THEME)!))
}
