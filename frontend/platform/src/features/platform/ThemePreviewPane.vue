<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { demoSiteUrl, liveSitePreview } from '@/services/hostMode'
import type { ThemeLook } from '@/services/platform'
import type { ThemeDef, ThemeMode } from '@rootsquares/ui/themes'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'

// The preview of a theme (W10-R13, W10-R14). With the demo site available (`demoSiteUrl`: the square app in demo mode, neutral sample content, no square's data) it shows
// that site in a frame (`<site>?demo=1&theme=<id>`: the real header, hero, events and footer, light or dark, desktop or phone width). The square's bridge (square/frontend/
// src/dev/previewBridge.ts) answers a hello message; without an answer (demo site not running) the sketch of design screen 9b is shown instead.
const props = withDefaults(defineProps<{ theme: ThemeDef; name: string; siteUrl?: string; mode?: ThemeMode; device?: 'desktop' | 'tablet' | 'phone'; sketchZoom?: number; interactive?: boolean; look?: ThemeLook | null; maxHeight?: number; clipHeight?: number; grow?: boolean; extraHeight?: number | Partial<Record<'desktop' | 'tablet' | 'phone', number>> }>(), {
  mode: 'light', device: 'desktop', sketchZoom: 1.3, interactive: false, maxHeight: 0, clipHeight: 0, grow: false, extraHeight: 0,
})
const { t } = useI18n()

const WIDE = { w: 1280, h: 800 }
const TABLET = { w: 768, h: 1000 }
const PHONE = { w: 427, h: 952 } // Pixel 9 Pro
const base = computed(() => props.siteUrl ?? demoSiteUrl)
const live = computed(() => liveSitePreview && !!base.value)
const state = ref<'loading' | 'ready' | 'off'>(live.value ? 'loading' : 'off')
const src = computed(() => (base.value ? `${base.value.replace(/\/?$/, '/')}?demo=1&theme=${encodeURIComponent(props.theme.id)}` : ''))
const origin = computed(() => { try { return new URL(base.value).origin } catch { return '' } })
// The address bar shows where the square would live, not the demo host the frame really loads (same words as the sketch).
const host = computed(() => `${props.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'your-square'}.rootsquares.com`)

const attempt = ref(0) // a new frame on every try
const frame = ref<HTMLIFrameElement | null>(null)
const box = ref<HTMLElement | null>(null)
const boxW = ref(0)
let ro: ResizeObserver | null = null
let helloTimer = 0
let loadTimer = 0

const size = computed(() => (props.device === 'phone' ? PHONE : props.device === 'tablet' ? TABLET : WIDE)) // the widths of the old preview chrome: 390, 768, 1280
const scale = computed(() => {
  if (!boxW.value) return 0.5
  const byWidth = boxW.value / size.value.w
  const byHeight = props.maxHeight ? props.maxHeight / size.value.h : Infinity
  return Math.min(byWidth, byHeight, props.grow ? Infinity : 1) // never enlarged (a phone or tablet frame in a wide box stays its real width), unless `grow`: the studio fills its well
})

// `clipHeight`: the shown height never passes this many px; the frame is made shorter (a shorter screen of the same width, the site scrolls inside it) instead of being shrunk.
// `extraHeight`: that many shown px added to the frame, one number for every device or one per device.
const frameH = computed(() => {
  const k = scale.value || 1
  const h = size.value.h + Math.round((typeof props.extraHeight === 'number' ? props.extraHeight : (props.extraHeight[props.device] ?? 0)) / k)
  return props.clipHeight ? Math.min(h, Math.round(props.clipHeight / k)) : h
})

function post(msg: Record<string, unknown>) { if (origin.value) frame.value?.contentWindow?.postMessage(msg, origin.value) }
function sendMode() { post({ type: 'rs-preview-mode', mode: props.mode }) }
// The owner's own colours and fonts (W18-R19): sent as plain data; the square app checks every value before it uses it.
// Plain copies: a reactive proxy cannot go through postMessage (DataCloneError).
function sendLook() {
  const c = props.look?.colors
  const d = props.look?.colors_dark
  post({ type: 'rs-preview-look', colors: c ? { bg: c.bg, ink: c.ink, acc: c.acc } : null, colors_dark: d ? { bg: d.bg, ink: d.ink, acc: d.acc } : null, fonts: props.look?.fonts ?? null, shape: props.look?.shape ? { ...props.look.shape } : null, feel: props.look?.feel ? { ...props.look.feel } : null, font_type: props.look?.type ? JSON.parse(JSON.stringify(props.look.type)) : null })
}
function onLoad() {
  window.clearTimeout(loadTimer)
  // The square site installs its answer a moment after the frame's load event, so a single hello can go unheard: ask every half second until it answers (W26-R32).
  stopHello()
  post({ type: 'rs-preview-hello' })
  helloPoll = window.setInterval(() => post({ type: 'rs-preview-hello' }), 500)
  window.clearTimeout(helloTimer)
  helloTimer = window.setTimeout(fail, 8000)
}
let helloPoll = 0
function stopHello() { window.clearInterval(helloPoll) }
// One automatic second try, then the card with a Retry button (W26-R31).
let tried = false
function fail() {
  stopHello()
  if (state.value !== 'loading') return
  if (!tried) { tried = true; retry(); return }
  state.value = 'off'
}
function retry() { attempt.value += 1; arm() }
function onMessage(e: MessageEvent) {
  if (e.origin !== origin.value || e.source !== frame.value?.contentWindow) return
  if ((e.data as { type?: string } | null)?.type === 'rs-preview-ready') { window.clearTimeout(helloTimer); stopHello(); state.value = 'ready'; sendLook(); sendMode() } // the chosen mode last: the look's own default mode must not win over the Light / Dark switch (TS-02)
}
function arm() {
  window.clearTimeout(loadTimer)
  if (!live.value) { state.value = 'off'; return }
  state.value = 'loading'
  loadTimer = window.setTimeout(fail, 15000)
}
watch(src, () => { tried = false; arm() })
watch(() => props.mode, () => { if (state.value === 'ready') sendMode() })
watch(() => props.look, () => { if (state.value === 'ready') { sendLook(); sendMode() } }, { deep: true })
onMounted(() => {
  window.addEventListener('message', onMessage)
  if (box.value && typeof ResizeObserver !== 'undefined') { ro = new ResizeObserver(([en]) => { boxW.value = en!.contentRect.width }); ro.observe(box.value) }
  arm()
})
onBeforeUnmount(() => { window.removeEventListener('message', onMessage); ro?.disconnect(); window.clearTimeout(helloTimer); window.clearTimeout(loadTimer); stopHello() })
</script>

<template>
  <div ref="box" class="tpl">
    <!-- The frame stays mounted while loading so the bridge can answer; the sketch shows until it does (and stays when it never does). -->
    <div v-if="live && state !== 'off'" class="tp-pv tpl-pv" :style="{ width: Math.round(size.w * scale) + 'px', margin: '0 auto' }">
      <div class="tp-pv-u"><i /><i /><i /><span>{{ host }}</span><small class="tpl-px">{{ size.w }}px</small></div>
      <div class="tpl-stage" :style="{ width: Math.round(size.w * scale) + 'px', height: Math.round(frameH * scale) + 'px' }">
        <iframe
          ref="frame"
          :key="origin + attempt"
          :src="src"
          class="tpl-frame"
          :class="{ 'tpl-frame--off': state !== 'ready', 'tpl-frame--still': !interactive }"
          :style="{ width: size.w + 'px', height: frameH + 'px', transform: `scale(${scale})` }"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
          :title="t('portal.theme.liveTitle', { theme: theme.name })"
          :tabindex="interactive ? 0 : -1"
          @load="onLoad"
        />
        <div v-if="state === 'loading'" class="tpl-wait" role="status" aria-live="polite">
          <span class="tpl-spin" aria-hidden="true"><i /><i /><i /></span>
          <b>{{ t('portal.theme.liveLoading') }}</b>
          <small>{{ t('portal.theme.liveLoadingSub') }}</small>
        </div>
      </div>
    </div>
    <!-- No drawing in its place (W26-R31): a sketch is not the customer's theme. An honest card with a retry instead. -->
    <div v-else class="tpl-off" role="status">
      <AppIcon name="refresh" :size="22" />
      <b>{{ t('portal.theme.liveOffTitle') }}</b>
      <small>{{ t('portal.theme.liveOff') }}</small>
      <AppButton v-if="live" variant="secondary" size="sm" icon="refresh" @click="retry">{{ t('portal.theme.liveRetry') }}</AppButton>
    </div>
  </div>
</template>

<style scoped>
.tpl { min-width: 0; width: 100%; }
.tpl-pv { max-width: 100%; }
.tpl-stage { position: relative; overflow: hidden; background: var(--color-surface-sunken); }
.tpl-frame { position: absolute; inset: 0 auto auto 0; border: 0; transform-origin: 0 0; background: #fff; }
.tpl-off { display: grid; justify-items: center; gap: 6px; text-align: center; padding: 40px 20px; border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-surface-sunken); color: var(--color-text-muted); }
.tpl-off b { margin-top: 6px; font-weight: 500; font-size: var(--text-sm); color: var(--color-text); }
.tpl-off small { font-size: var(--text-xs); max-width: 44ch; margin-bottom: 8px; }
.tpl-frame--off { visibility: hidden; }
.tpl-frame--still { pointer-events: none; }
/* Loading: a shimmer ground and a layered brass spinner (sweeping ring, counter-turning dashed ring, breathing centre). Still when motion is reduced. */
.tpl-wait { position: absolute; inset: 0; display: grid; place-content: center; justify-items: center; gap: 6px; text-align: center; padding: 16px;
  background: linear-gradient(100deg, var(--color-surface-sunken) 30%, var(--color-surface) 50%, var(--color-surface-sunken) 70%) 0 0 / 200% 100%; animation: tpl-shim 2.2s ease-in-out infinite; }
.tpl-wait b { margin-top: 14px; font-weight: 500; font-size: var(--text-sm); color: var(--color-text); }
.tpl-wait small { font-size: var(--text-xs); color: var(--color-text-muted); }
.tpl-spin { position: relative; width: 76px; height: 76px; display: block; }
.tpl-spin i { position: absolute; border-radius: 50%; display: block; }
.tpl-spin i:nth-child(1) { inset: 0; background: conic-gradient(from 0deg, transparent 0 22%, var(--color-brass) 100%); -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 6px), #000 calc(100% - 5px)); mask: radial-gradient(farthest-side, transparent calc(100% - 6px), #000 calc(100% - 5px)); animation: tpl-turn 1.1s linear infinite; }
.tpl-spin i:nth-child(2) { inset: 13px; border: 2px dashed var(--color-brass); opacity: 0.45; animation: tpl-turn 2.4s linear infinite reverse; }
.tpl-spin i:nth-child(3) { inset: 31px; background: var(--color-brass); animation: tpl-breathe 1.4s ease-in-out infinite; }
@keyframes tpl-turn { to { transform: rotate(360deg); } }
@keyframes tpl-breathe { 0%, 100% { transform: scale(0.6); opacity: 0.55; } 50% { transform: scale(1); opacity: 1; } }
@keyframes tpl-shim { to { background-position: -200% 0; } }
@media (prefers-reduced-motion: reduce) { .tpl-wait, .tpl-spin i { animation: none; } }
.tpl-px { margin-inline-start: auto; opacity: 0.6; font-size: 10px; }
.tp-pv-u span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } /* the address never wraps in a small frame (TS-22) */
.tp-pv-u small { flex: none; }
</style>
