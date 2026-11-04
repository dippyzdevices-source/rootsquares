<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, type Component } from 'vue'
import { useAdminPreview } from '../composables/useAdminPreview'
import { activeLayout, compactBelow, shellOf, type ShellKind } from './layouts'
import { compact, medium, wide } from './useSiteLayout'
import { ensureBasics } from './useSiteData'
import ShellCompact from './shells/ShellCompact.vue'

// The public pages of a themed square (W9-R5): the theme's shell around the page. Above 860 px (measured on this container, not the window) the
// theme's own header, navigation and footer arrangement; below it every theme uses the compact header. The shells load per theme (code split).
const layout = activeLayout!
const SHELLS: Partial<Record<ShellKind, Component>> = {
  engine: defineAsyncComponent(() => import('./engine/EngineShell.vue')),
  harvest: defineAsyncComponent(() => import('./shells/ShellHarvest.vue')),
  still: defineAsyncComponent(() => import('./shells/ShellStill.vue')),
  fjord: defineAsyncComponent(() => import('./shells/ShellFjord.vue')),
  pencil: defineAsyncComponent(() => import('./shells/ShellPencil.vue')),
  olive: defineAsyncComponent(() => import('./shells/ShellOlive.vue')),
  berry: defineAsyncComponent(() => import('./shells/ShellBerry.vue')),
  ledger: defineAsyncComponent(() => import('./shells/ShellLedger.vue')),
  marquee: defineAsyncComponent(() => import('./shells/ShellMarquee.vue')),
  bar: defineAsyncComponent(() => import('./shells/ShellBar.vue')),
  neubar: defineAsyncComponent(() => import('./shells/ShellNeubar.vue')),
  rail: defineAsyncComponent(() => import('./shells/ShellRail.vue')),
  saas: defineAsyncComponent(() => import('./shells/ShellSaas.vue')),
  dock: defineAsyncComponent(() => import('./shells/ShellDock.vue')),
  torn: defineAsyncComponent(() => import('./shells/ShellTorn.vue')),
}
const shell = computed(() => (compact.value ? ShellCompact : SHELLS[shellOf(layout)]!))
const { adminPreviewActive } = useAdminPreview()

const root = ref<HTMLElement | null>(null)
let observer: ResizeObserver | null = null
const measure = () => {
  if (!root.value) return
  compact.value = root.value.clientWidth < compactBelow(layout)
  medium.value = root.value.clientWidth < 1100
  wide.value = root.value.clientWidth >= 1280
}
onMounted(() => {
  ensureBasics()
  measure()
  if (typeof ResizeObserver !== 'undefined' && root.value) {
    observer = new ResizeObserver(measure)
    observer.observe(root.value)
  }
})
onBeforeUnmount(() => observer?.disconnect())

const vars = {
  '--lt-mw': `${layout.mw}px`,
  '--lt-px': `${layout.px}px`,
  '--lt-r': `${layout.r}px`,
  '--lt-dw': String(layout.dw),
  ...(layout.ir ? { '--lt-ir': layout.ir } : {}),
}
</script>

<template>
  <div
    ref="root"
    class="ds-scope lt-site"
    :class="[`lt-theme-${layout.shell}`, { 'is-compact': compact, 'is-medium': medium, 'lt-caps': layout.caps, 'lt-neu': layout.neu, 'lt-emn': layout.emn, 'lt-emc-pa': layout.emc === 'pa', 'lt-engine': layout.engine }]"
    :data-lt-shell="layout.shell"
    :style="vars"
  >
    <a href="#lt-main" class="lt-skip">Skip to content</a>
    <component :is="shell">
      <div v-if="adminPreviewActive" class="admin-preview-banner ds-alert ds-alert-info" role="status" style="border-radius: 0; justify-content: center; text-align: center">
        <div><strong>Admin preview</strong> — this page isn't published yet. Only signed-in admins can see it.</div>
      </div>
      <main id="lt-main" class="lt-main" tabindex="-1">
        <slot><router-view /></slot>
      </main>
    </component>
  </div>
</template>
