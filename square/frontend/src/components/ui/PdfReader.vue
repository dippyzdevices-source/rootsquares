<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import BaseLoadingState from './BaseLoadingState.vue'
import { loadPdfJs } from '../../utils/pdfjs'

const props = defineProps<{ url: string; title?: string; closable?: boolean }>()
const emit = defineEmits<{ close: [] }>()

const ZOOM_STEPS = [0.75, 1, 1.25, 1.5, 2, 3]

const root = ref<HTMLElement | null>(null)
const stage = ref<HTMLElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)

const loading = ref(true)
const error = ref(false)
const errorDetail = ref('')
const pageNumber = ref(1)
const numPages = ref(0)
const zoomIndex = ref(1)
const pageInput = ref('1')
const isFullscreen = ref(false)

// pdf.js document/render-task handles are plain objects, kept out of Vue reactivity.
let loadingTask: import('pdfjs-dist').PDFDocumentLoadingTask | null = null
let doc: import('pdfjs-dist').PDFDocumentProxy | null = null
let renderTask: import('pdfjs-dist').RenderTask | null = null
let resizeObserver: ResizeObserver | null = null
let lastWidth = 0
let destroyed = false

const zoom = computed(() => ZOOM_STEPS[zoomIndex.value])
const canPrev = computed(() => pageNumber.value > 1)
const canNext = computed(() => pageNumber.value < numPages.value)

async function renderPage() {
  if (!doc || !canvas.value || !stage.value) return
  try {
    renderTask?.cancel()
    const page = await doc.getPage(pageNumber.value)
    const base = page.getViewport({ scale: 1 })
    const available = stage.value.clientWidth || base.width
    const scale = (available / base.width) * zoom.value
    const viewport = page.getViewport({ scale })
    const dpr = window.devicePixelRatio || 1
    const el = canvas.value
    el.width = Math.floor(viewport.width * dpr)
    el.height = Math.floor(viewport.height * dpr)
    el.style.width = `${Math.floor(viewport.width)}px`
    el.style.height = `${Math.floor(viewport.height)}px`
    const ctx = el.getContext('2d')
    if (!ctx) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    renderTask = page.render({ canvasContext: ctx, canvas: el, viewport })
    await renderTask.promise
  } catch (err) {
    // A cancelled render (page flipped mid-render) is expected, not an error.
    if ((err as { name?: string })?.name !== 'RenderingCancelledException') error.value = true
  }
}

async function load() {
  loading.value = true
  error.value = false
  try {
    const pdfjs = await loadPdfJs()
    void loadingTask?.destroy()
    // Plain whole-file GET: no Range header, so a cross-origin bucket needs no CORS preflight (a Range
    // request is not CORS-safelisted and fails on buckets that don't allow that header).
    const task = pdfjs.getDocument({ url: props.url, disableRange: true, disableStream: true })
    loadingTask = task
    doc = await task.promise
    if (destroyed) {
      void task.destroy()
      return
    }
    numPages.value = doc.numPages
    pageNumber.value = 1
    loading.value = false
    await nextTick()
    await renderPage()
  } catch (err) {
    // Surface the real reason (CORS, 404, a bad file …) — "could not open" alone can't be diagnosed.
    console.error('[PdfReader] could not open', props.url, err)
    errorDetail.value = err instanceof Error ? err.message : String(err)
    error.value = true
    loading.value = false
  }
}

function goTo(n: number) {
  const clamped = Math.min(Math.max(1, Math.round(n)), numPages.value || 1)
  pageNumber.value = clamped
  pageInput.value = String(clamped)
}
function commitPageInput() {
  const n = Number(pageInput.value)
  if (Number.isFinite(n)) goTo(n)
  else pageInput.value = String(pageNumber.value)
}
function zoomBy(delta: number) {
  zoomIndex.value = Math.min(Math.max(0, zoomIndex.value + delta), ZOOM_STEPS.length - 1)
}

// Leaves full screen first (if on), then lets the page decide where "close" goes.
async function closeReader() {
  if (document.fullscreenElement) await document.exitFullscreen()
  emit('close')
}

async function toggleFullscreen() {
  if (!root.value) return
  if (document.fullscreenElement) await document.exitFullscreen()
  else await root.value.requestFullscreen?.()
}
function onFullscreenChange() {
  isFullscreen.value = document.fullscreenElement === root.value
}

function onKeydown(event: KeyboardEvent) {
  if ((event.target as HTMLElement)?.tagName === 'INPUT') return
  if (event.key === 'ArrowRight' || event.key === 'PageDown') goTo(pageNumber.value + 1)
  else if (event.key === 'ArrowLeft' || event.key === 'PageUp') goTo(pageNumber.value - 1)
  else return
  event.preventDefault()
}

// Swipe to turn pages on touch screens: only a clearly horizontal gesture while not zoomed in,
// so vertical scrolling and panning a zoomed page are untouched.
let touchStartX = 0
let touchStartY = 0
function onTouchStart(event: TouchEvent) {
  touchStartX = event.changedTouches[0].clientX
  touchStartY = event.changedTouches[0].clientY
}
function onTouchEnd(event: TouchEvent) {
  const dx = event.changedTouches[0].clientX - touchStartX
  const dy = event.changedTouches[0].clientY - touchStartY
  if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 2 && zoomIndex.value <= 1) {
    goTo(pageNumber.value + (dx < 0 ? 1 : -1))
  }
}

watch([pageNumber, zoomIndex], () => {
  pageInput.value = String(pageNumber.value)
  void renderPage()
})
watch(() => props.url, load)

onMounted(() => {
  void load()
  document.addEventListener('fullscreenchange', onFullscreenChange)
  if (stage.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => {
      const width = stage.value?.clientWidth ?? 0
      if (width && Math.abs(width - lastWidth) > 2) {
        lastWidth = width
        void renderPage()
      }
    })
    resizeObserver.observe(stage.value)
  }
})
onBeforeUnmount(() => {
  destroyed = true
  renderTask?.cancel()
  resizeObserver?.disconnect()
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  void loadingTask?.destroy()
})
</script>

<template>
  <div
    ref="root"
    class="pdf-reader ds-scope"
    :class="{ 'pdf-reader--fullscreen': isFullscreen }"
    tabindex="0"
    role="group"
    :aria-label="title ? `Reader: ${title}` : 'PDF reader'"
    @keydown="onKeydown"
  >
    <div class="pdf-toolbar">
      <div class="pdf-toolbar-group">
        <button type="button" class="pdf-btn" :disabled="!canPrev" aria-label="Previous page" @click="goTo(pageNumber - 1)">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6" /></svg>
        </button>
        <span class="pdf-pages">
          <input
            v-model="pageInput"
            class="pdf-page-input"
            inputmode="numeric"
            aria-label="Page number"
            :disabled="numPages === 0"
            @change="commitPageInput"
            @keydown.enter.prevent="commitPageInput"
          />
          <span class="ds-meta">/ {{ numPages || '–' }}</span>
        </span>
        <button type="button" class="pdf-btn" :disabled="!canNext" aria-label="Next page" @click="goTo(pageNumber + 1)">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6" /></svg>
        </button>
      </div>
      <div class="pdf-toolbar-group">
        <button type="button" class="pdf-btn" :disabled="zoomIndex === 0" aria-label="Zoom out" @click="zoomBy(-1)">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /></svg>
        </button>
        <span class="ds-meta pdf-zoom">{{ Math.round(zoom * 100) }}%</span>
        <button type="button" class="pdf-btn" :disabled="zoomIndex === ZOOM_STEPS.length - 1" aria-label="Zoom in" @click="zoomBy(1)">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
        </button>
        <button type="button" class="pdf-btn" :aria-label="isFullscreen ? 'Exit full screen' : 'Full screen'" @click="toggleFullscreen">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3" /></svg>
        </button>
        <a :href="url" download target="_blank" rel="noopener" class="pdf-btn" aria-label="Download PDF">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="m7 10 5 5 5-5" /><path d="M12 15V3" /></svg>
        </a>
        <button v-if="closable" type="button" class="pdf-btn pdf-close" aria-label="Close magazine" title="Close magazine" @click="closeReader">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18" /><path d="m6 6 12 12" /></svg>
        </button>
      </div>
    </div>

    <div ref="stage" class="pdf-stage" @touchstart.passive="onTouchStart" @touchend.passive="onTouchEnd">
      <BaseLoadingState v-if="loading" label="Loading magazine…" />
      <div v-else-if="error" class="pdf-error ds-card ds-card-sunken">
        <h3 class="ds-subtitle">Could not open this magazine here</h3>
        <p class="ds-meta" style="margin-top: var(--ds-space-2)">
          <a :href="url" target="_blank" rel="noopener" class="pdf-fallback">Open or download the PDF</a> instead.
        </p>
        <p v-if="errorDetail" class="ds-caption pdf-error-detail" style="margin-top: var(--ds-space-2)">{{ errorDetail }}</p>
      </div>
      <canvas v-show="!loading && !error" ref="canvas" class="pdf-canvas" :aria-label="`Page ${pageNumber} of ${numPages}`" />
    </div>
  </div>
</template>

<style scoped>
.pdf-reader {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-3);
  outline: none;
}
.pdf-reader--fullscreen {
  padding: var(--ds-space-4);
  background: var(--ds-surface-page, #fff);
}
.pdf-reader--fullscreen .pdf-stage {
  max-height: none;
  flex: 1;
}
.pdf-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-3);
  flex-wrap: wrap;
  padding: var(--ds-space-2) var(--ds-space-3);
  border: 1px solid var(--ds-border-hairline);
  border-radius: 8px;
}
.pdf-toolbar-group {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
}
.pdf-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--ds-border-hairline);
  border-radius: 8px;
  background: transparent;
  color: var(--ds-text-heading, inherit);
  cursor: pointer;
  text-decoration: none;
}
.pdf-btn:hover:not(:disabled) {
  background: var(--ds-action-ghost-hover);
}
.pdf-btn:disabled {
  opacity: 0.4;
  cursor: default;
}
.pdf-pages {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.pdf-page-input {
  width: 48px;
  height: 36px;
  text-align: center;
  border: 1px solid var(--ds-border-hairline);
  border-radius: 8px;
  background: transparent;
  color: inherit;
  font: inherit;
}
.pdf-zoom {
  min-width: 44px;
  text-align: center;
}
.pdf-stage {
  overflow: auto;
  max-height: 80vh;
  border: 1px solid var(--ds-border-hairline);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.04);
}
.pdf-canvas {
  display: block;
  margin: 0 auto;
  background: #fff;
  max-width: none;
}
.pdf-error {
  text-align: center;
  padding: var(--ds-space-8);
}
.pdf-fallback {
  color: var(--ds-action-primary);
  text-decoration: underline;
}
</style>
