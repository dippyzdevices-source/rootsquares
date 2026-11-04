<script setup lang="ts">
import { Teleport, computed, nextTick, onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import IconButton from '@/components/ui/IconButton.vue'
import SegToggle from '@/components/ui/SegToggle.vue'
import { THEME_COLORS } from '@/themes/colors'
import type { ThemeDef, ThemeMode } from '@rootsquares/ui/themes'
import type { ThemeLook } from '@/services/platform'
import ThemePreviewPane from './ThemePreviewPane.vue'

// Full-size preview of a theme (W10-R11), the same controls as the public Templates page: light or dark, desktop or phone, previous / next theme (arrow keys too),
// Apply from inside (`applyLabel` renames the button: "Start your website" on the public Templates page, W10-R25). Shows the real square site when it is running (ThemePreviewPane), else the sketch. Teleported modal with a focus trap, Escape and focus return, like ConfirmDialog.
const props = defineProps<{ themes: ThemeDef[]; themeId: string; name: string; currentId?: string; canApply?: boolean; busy?: boolean; applyLabel?: string; look?: ThemeLook | null }>()
const emit = defineEmits<{ 'update:themeId': [id: string]; close: []; apply: [] }>()

const { t } = useI18n()
const id = useId()
const mode = ref<ThemeMode>('light')
const device = ref<'desktop' | 'tablet' | 'phone'>('desktop')
const box = ref<HTMLElement | null>(null)
const stageMax = Math.max(380, (typeof window === 'undefined' ? 900 : window.innerHeight) - 340)
let opener: Element | null = null

const index = computed(() => props.themes.findIndex((x) => x.id === props.themeId))
const theme = computed(() => props.themes[index.value] ?? props.themes[0]!)
const sw = computed(() => THEME_COLORS[theme.value.id]!.light)
function go(step: number) {
  const n = props.themes.length
  if (n < 2) return
  const from = index.value < 0 ? (step > 0 ? -1 : 0) : index.value
  emit('update:themeId', props.themes[(from + step + n) % n]!.id)
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') { e.preventDefault(); emit('close'); return }
  const inField = (e.target as HTMLElement | null)?.closest('input,select,textarea')
  if (!inField && e.key === 'ArrowLeft') { e.preventDefault(); go(-1) }
  else if (!inField && e.key === 'ArrowRight') { e.preventDefault(); go(1) }
  else if (e.key === 'Tab' && box.value) {
    const f = [...box.value.querySelectorAll<HTMLElement>('a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])')]
    if (!f.length) return
    const first = f[0]!, last = f[f.length - 1]!
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
  }
}
onMounted(async () => {
  opener = document.activeElement
  document.addEventListener('keydown', onKey)
  document.body.style.overflow = 'hidden'
  await nextTick()
  box.value?.querySelector<HTMLElement>('button')?.focus()
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
  ;(opener as HTMLElement | null)?.focus?.()
})
</script>

<template>
  <Teleport to="body">
    <div class="rs rs-modal-host tpd-host" style="position: fixed" @mousedown="(e) => e.target === e.currentTarget && emit('close')">
      <div ref="box" class="tpd" role="dialog" aria-modal="true" :aria-labelledby="`${id}-t`">
        <header class="tpd-hd">
          <div class="tpd-title">
            <i class="tp-sw"><b :style="{ background: sw.bg }" /><b :style="{ background: sw.ink }" /><b :style="{ background: sw.accent }" /></i>
            <span>
              <b :id="`${id}-t`">{{ t('portal.theme.dlgTitle', { theme: theme.name }) }}<span v-if="theme.id === currentId" class="rs-chip rs-chip--info">{{ t('portal.theme.inUse') }}</span></b>
              <small>{{ theme.shellLabel }} · {{ theme.colour }} · {{ theme.display }} / {{ theme.body }}</small>
            </span>
          </div>
          <IconButton icon="x" :label="t('portal.theme.close')" @click="emit('close')" />
        </header>

        <div class="tpd-bar">
          <div v-if="themes.length > 1" class="tpd-nav" role="group" :aria-label="t('portal.theme.listLabel')">
            <IconButton icon="chevron-left" :label="t('portal.theme.prev')" :disabled="themes.length < 2" @click="go(-1)" />
            <select class="rs-input tpd-pick" :value="theme.id" :aria-label="t('portal.theme.pickLabel')" @change="emit('update:themeId', ($event.target as HTMLSelectElement).value)">
              <option v-for="(x, i) in themes" :key="x.id" :value="x.id">{{ i + 1 }}. {{ x.name }}</option>
            </select>
            <IconButton icon="chevron-right" :label="t('portal.theme.next')" :disabled="themes.length < 2" @click="go(1)" />
          </div>
          <SegToggle v-model="mode" :label="t('portal.theme.mode')" :items="[['light', t('portal.theme.light')], ['dark', t('portal.theme.dark')]]" />
          <SegToggle v-model="device" :label="t('portal.theme.device')" :items="[['desktop', t('portal.theme.desktop')], ['tablet', t('portal.theme.tablet')], ['phone', t('portal.theme.phone')]]" />
        </div>

        <div class="tpd-stage"><ThemePreviewPane :theme="theme" :name="name" :mode="mode" :device="device" :sketch-zoom="device === 'phone' ? 1.5 : 2" :max-height="stageMax" :look="look" interactive /></div>

        <footer class="tpd-ft">
          <AppButton icon="x" variant="secondary" @click="emit('close')">{{ t('portal.theme.close') }}</AppButton>
          <AppButton v-if="canApply" icon="check" :disabled="theme.id === currentId" :loading="busy" @click="emit('apply')">{{ applyLabel ?? t('portal.theme.save') }}</AppButton>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.tpd-pick { width: auto; min-width: 200px; max-width: 280px; }
.tpd-host { z-index: 80; align-items: center; justify-content: center; padding: 20px; background: var(--color-overlay); }
.tpd { width: min(1040px, 100%); max-height: calc(100vh - 40px); display: grid; grid-template-rows: auto auto minmax(0, 1fr) auto; gap: 16px; padding: 22px 24px; background: var(--color-surface-raised); border: 1px solid var(--color-border); border-radius: var(--radius-lg); box-shadow: var(--shadow-md); }
.tpd-hd { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.tpd-title { display: flex; gap: 14px; align-items: center; min-width: 0; }
.tpd-title > span { display: grid; gap: 3px; min-width: 0; }
.tpd-title b { font-weight: 500; font-size: var(--text-lg); display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.tpd-title small { color: var(--color-text-muted); font-size: var(--text-xs); overflow-wrap: anywhere; }
.tpd-bar { display: flex; flex-wrap: wrap; gap: 14px 22px; align-items: center; }
.tpd-nav { display: flex; align-items: center; gap: 6px; }
.tpd-pos { min-width: 70px; text-align: center; font-size: var(--text-xs); color: var(--color-text-muted); }
.tpd-stage { overflow: auto; padding: 4px; min-height: 0; }
.tpd-ft { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 10px; }
@media (max-width: 640px) {
  .tpd-host { padding: 0; align-items: flex-end; }
  .tpd { max-height: 100vh; height: 100%; border-radius: 0; padding: 16px; }
  .tpd-ft > * { flex: 1; min-height: 44px; justify-content: center; }
}
</style>
