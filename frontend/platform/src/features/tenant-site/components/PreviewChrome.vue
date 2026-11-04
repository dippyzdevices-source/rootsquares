<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { THEMES, type ThemeMode } from '@rootsquares/ui/themes'
import { THEME_COLORS } from '@/themes/colors'
import { DEVICES, type Device } from '../previewDevices'

// Design v3 Preview chrome (screens/G.jsx 6, export/screens.md "Extension" 6): floating hairline bar with a theme picker (listbox with swatches),
// light/dark toggle, device width (phone 390 / tablet 768 / desktop 1280, px readout) and Exit. The only element with the overlay shadow.
// Replaces the earlier SiteSwitcher. The device switch is hidden on small screens (as in the design's mobile frame).
const props = defineProps<{ themeId: string; mode: ThemeMode; device: Device }>()
const emit = defineEmits<{ 'update:themeId': [v: string]; 'update:mode': [v: ThemeMode]; 'update:device': [v: Device] }>()

const { t } = useI18n()
const router = useRouter()
const open = ref(false)
const root = ref<HTMLElement | null>(null)
const btn = ref<HTMLButtonElement | null>(null)
const listId = useId()
const current = () => THEMES.find((x) => x.id === props.themeId) ?? THEMES[0]!
const sw = (id: string) => THEME_COLORS[id]!.light

const optionEls = () => [...(root.value?.querySelectorAll<HTMLElement>('[role=option]') ?? [])]
async function show() {
  open.value = true
  document.addEventListener('mousedown', outside)
  await nextTick()
  const els = optionEls()
  ;(els.find((e) => e.getAttribute('aria-selected') === 'true') ?? els[0])?.focus()
}
function hide(refocus = true) {
  open.value = false
  document.removeEventListener('mousedown', outside)
  if (refocus) btn.value?.focus()
}
const outside = (e: MouseEvent) => { if (root.value && !root.value.contains(e.target as Node)) hide(false) }
function onKey(e: KeyboardEvent) {
  const els = optionEls()
  const i = els.indexOf(document.activeElement as HTMLElement)
  if (e.key === 'Escape') { e.preventDefault(); hide() }
  else if (e.key === 'ArrowDown') { e.preventDefault(); els[(i + 1) % els.length]?.focus() }
  else if (e.key === 'ArrowUp') { e.preventDefault(); els[(i - 1 + els.length) % els.length]?.focus() }
  else if (e.key === 'Home') { e.preventDefault(); els[0]?.focus() }
  else if (e.key === 'End') { e.preventDefault(); els[els.length - 1]?.focus() }
  else if (e.key === 'Tab') hide(false)
}
function pick(id: string) { emit('update:themeId', id); hide() }
onBeforeUnmount(() => document.removeEventListener('mousedown', outside))
</script>

<template>
  <div class="bx-pc" role="toolbar" :aria-label="t('pv.label')">
    <!-- Theme picker is hidden while only one theme is enabled (src/themes/index.ts) -->
    <div v-if="THEMES.length > 1" ref="root" style="position: relative">
      <button ref="btn" type="button" class="rs-btn rs-btn--secondary rs-btn--sm" aria-haspopup="listbox" :aria-expanded="open" :aria-controls="open ? listId : undefined" @click="open ? hide() : show()" @keydown.arrow-down.prevent="!open && show()">
        <span class="pv-sw"><i :style="{ background: sw(current().id).bg }" /><i :style="{ background: sw(current().id).ink }" /><i :style="{ background: sw(current().id).accent }" /></span>{{ current().name }}<AppIcon name="chevron-down" :size="12" />
      </button>
      <div v-if="open" :id="listId" class="bx-pop pv-list" role="listbox" :aria-label="t('pv.theme')" @keydown="onKey">
        <button v-for="x in THEMES" :key="x.id" type="button" role="option" :aria-selected="x.id === themeId" style="justify-content: space-between" @click="pick(x.id)">
          <span class="bs-row"><span class="pv-sw pv-sw--sm"><i :style="{ background: sw(x.id).bg }" /><i :style="{ background: sw(x.id).ink }" /><i :style="{ background: sw(x.id).accent }" /></span>{{ x.name }}</span>
          <AppIcon v-if="x.id === themeId" name="check" :size="13" />
        </button>
      </div>
    </div>
    <span v-if="THEMES.length > 1" class="sep" />
    <div class="bt-seg">
      <div role="group" :aria-label="t('pv.colourMode')">
        <button type="button" :aria-pressed="mode === 'light'" :aria-label="t('pv.light')" @click="emit('update:mode', 'light')"><AppIcon name="sun" :size="15" /></button>
        <button type="button" :aria-pressed="mode === 'dark'" :aria-label="t('pv.dark')" @click="emit('update:mode', 'dark')"><AppIcon name="moon" :size="15" /></button>
      </div>
    </div>
    <span class="sep pv-device" />
    <div class="bt-seg pv-device">
      <div role="group" :aria-label="t('pv.deviceWidth')">
        <button v-for="(d, k) in DEVICES" :key="k" type="button" :aria-pressed="device === k" :aria-label="t('pv.deviceLabel', { name: t(`pv.devices.${k}`), px: d.px })" :title="t(`pv.devices.${k}`)" @click="emit('update:device', k)"><AppIcon :name="d.icon" :size="15" /></button>
      </div>
    </div>
    <span class="bs-mute pv-device" style="font-size: var(--text-xs); min-width: 48px">{{ DEVICES[device].px }}px</span>
    <span class="sep" />
    <button type="button" class="rs-btn rs-btn--ghost rs-btn--sm" @click="router.push('/templates')"><AppIcon name="out" :size="14" />{{ t('pv.exit') }}</button>
  </div>
</template>
