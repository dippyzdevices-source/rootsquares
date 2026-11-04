<script setup lang="ts">
import { computed, provide, watchEffect } from 'vue'
import { DEFAULT_TENANT_THEME, getTheme, type ThemeMode } from '@rootsquares/ui/themes'
import { loadThemeFonts } from '@/themes/fonts'
import { THEME_LAYOUT_KEY } from './themeScope'

// Wraps a subtree in a tenant theme (tenant public site only). Only CSS variables change, never markup.
const props = withDefaults(defineProps<{ theme?: string; mode?: ThemeMode }>(), { theme: DEFAULT_TENANT_THEME, mode: 'light' })

const layout = computed(() => getTheme(props.theme) ?? getTheme(DEFAULT_TENANT_THEME)!)
provide(THEME_LAYOUT_KEY, layout)
// Self-hosted fonts of the active theme only (code-split); system fallbacks until loaded
watchEffect(() => { void loadThemeFonts(props.theme) })
</script>

<template>
  <div :data-theme="theme" :data-mode="mode" class="min-w-0" style="background: var(--t-bg); color: var(--t-text); font-family: var(--t-font-body)">
    <slot />
  </div>
</template>
