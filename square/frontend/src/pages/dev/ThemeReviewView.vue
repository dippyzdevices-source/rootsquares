<script setup lang="ts">
import { computed, ref } from 'vue'
import { GENERATED_ENGINES, GENERATED_LAYOUTS } from '../../layout-themes/layouts.generated'

/*
 * What it is:   The theme review page, /theme-review (W10-R6).
 * What it does: Shows every theme of the square app side by side as a small live preview (an iframe of the square itself with `?theme=<id>`), light or dark,
 *               on the page chosen, filtered by name or kind; clicking a card opens that theme full size in a new tab. Each card has a **Keep** checkbox (remembered in this browser; counter, "Kept only" filter, Copy list, Clear). The cards use the neutral demo data (`?demo=1`, checkbox "Demo data", on by default). Asserts nothing: a person looks.
 * How to use:   Development only: the route exists only when running `vite` (router/index.ts, import.meta.env.DEV), never in a production build.
 * Run:          from square/frontend: npm run dev, then http://<slug>.localhost:5274/theme-review (guide 32).
 * Read before:  docs/setup/21-layout-themes.md (the themes and `?theme=`).
 * Read after:   docs/setup/32-theme-review.md (what to check, limits, troubleshooting); scripts/test-themes.ps1 for the automated checks.
 */
type Row = { id: string; name: string; shell: string; kind: 'engine' | 'reference' }
const rows: Row[] = [
  ...Object.entries(GENERATED_ENGINES).map(([id, t]) => ({ id, name: t.name, shell: t.shell, kind: 'engine' as const })),
  ...Object.entries(GENERATED_LAYOUTS).map(([id, t]) => ({ id, name: t.name, shell: t.shell, kind: 'reference' as const })),
]
const dark = ref(false)
const path = ref('/')
const query = ref('')
const demo = ref(true) // neutral sample data on every card and link (W18-R42); off = the square's own data
const href = (id: string) => `${path.value}?${demo.value ? 'demo=1&' : ''}theme=${id}`
const kind = ref<'all' | 'engine' | 'reference'>('all')
// The themes ticked "Keep" (W18-R43): remembered in this browser only, so a shortlist survives a reload; nothing leaves the page.
const KEEP_KEY = 'rs-theme-review-keep'
function loadKept(): string[] {
  try { const v = JSON.parse(window.localStorage.getItem(KEEP_KEY) ?? '[]'); return Array.isArray(v) ? v.filter((x) => typeof x === 'string' && rows.some((r) => r.id === x)) : [] } catch { return [] }
}
const kept = ref<string[]>(loadKept())
const onlyKept = ref(false)
const copied = ref(false)
function toggleKeep(id: string): void {
  kept.value = kept.value.includes(id) ? kept.value.filter((x) => x !== id) : [...kept.value, id]
  try { window.localStorage.setItem(KEEP_KEY, JSON.stringify(kept.value)) } catch { /* storage blocked: the list lasts until the page closes */ }
  copied.value = false
}
function clearKept(): void { kept.value = []; try { window.localStorage.removeItem(KEEP_KEY) } catch { /* nothing stored */ } }
async function copyKept(): Promise<void> {
  try { await navigator.clipboard.writeText(kept.value.join('\n')); copied.value = true } catch { copied.value = false }
}
const shown = computed(() => rows.filter((r) => (kind.value === 'all' || r.kind === kind.value) && (!onlyKept.value || kept.value.includes(r.id)) && `${r.id} ${r.name} ${r.shell}`.toLowerCase().includes(query.value.toLowerCase())))
const W = 1280
const H = 800
const SCALE = 0.3
function applyMode(e: Event): void {
  const doc = (e.target as HTMLIFrameElement).contentDocument
  doc?.documentElement.classList.toggle('dark', dark.value)
}
function toggle(): void {
  dark.value = !dark.value
  document.querySelectorAll<HTMLIFrameElement>('iframe.tr-frame').forEach((f) => f.contentDocument?.documentElement.classList.toggle('dark', dark.value))
}
</script>

<template>
  <div class="tr">
    <header class="tr-bar">
      <strong>Theme review</strong>
      <input v-model="query" type="search" placeholder="Filter by name, id or shell" />
      <select v-model="kind"><option value="all">All themes</option><option value="engine">Engine themes</option><option value="reference">Reference layouts</option></select>
      <select v-model="path"><option value="/">Home</option><option value="/events">Events</option><option value="/membership">Membership</option><option value="/gallery">Gallery</option><option value="/contact">Contact</option><option value="/login">Sign in</option></select>
      <label class="tr-demo"><input v-model="demo" type="checkbox" /> Demo data</label>
      <button type="button" @click="toggle">{{ dark ? 'Dark' : 'Light' }}</button>
      <span>{{ shown.length }} themes</span>
      <label class="tr-demo"><input v-model="onlyKept" type="checkbox" /> Kept only</label>
      <b class="tr-kept">{{ kept.length }} kept</b>
      <button v-if="kept.length" type="button" @click="copyKept">{{ copied ? 'Copied' : 'Copy list' }}</button>
      <button v-if="kept.length" type="button" @click="clearKept">Clear</button>
    </header>
    <p v-if="kept.length" class="tr-list">Kept: {{ kept.join(', ') }}</p>
    <div class="tr-grid">
      <figure v-for="r in shown" :key="r.id + path + demo" class="tr-card">
        <a :href="href(r.id)" target="_blank" rel="noopener" class="tr-view" :style="{ width: `${W * SCALE}px`, height: `${H * SCALE}px` }">
          <iframe class="tr-frame" :src="href(r.id)" loading="lazy" :style="{ width: `${W}px`, height: `${H}px`, transform: `scale(${SCALE})` }" tabindex="-1" title="" @load="applyMode" />
        </a>
        <figcaption>
          <label class="tr-keep"><input type="checkbox" :checked="kept.includes(r.id)" @change="toggleKeep(r.id)" /> Keep</label>
          <b>{{ r.name }}</b> <small>{{ r.id }} · {{ r.shell }} · {{ r.kind }}</small>
        </figcaption>
      </figure>
    </div>
  </div>
</template>

<style scoped>
.tr { font: 14px system-ui, sans-serif; background: #f2f2f2; min-height: 100vh; color: #222; }
.tr-bar { position: sticky; top: 0; z-index: 5; display: flex; gap: 12px; align-items: center; padding: 10px 16px; background: #fff; border-bottom: 1px solid #ddd; flex-wrap: wrap; }
.tr-bar input, .tr-bar select, .tr-bar button { height: 34px; padding: 0 10px; border: 1px solid #bbb; border-radius: 6px; background: #fff; }
.tr-demo { display: inline-flex; align-items: center; gap: 6px; }
.tr-kept { margin-inline-start: auto; }
.tr-list { margin: 0; padding: 8px 16px; background: #fff8e1; border-bottom: 1px solid #e6d9a8; font-size: 13px; }
.tr-keep { display: inline-flex; align-items: center; gap: 5px; margin-inline-end: 8px; font-weight: 600; cursor: pointer; }
.tr-grid { display: flex; flex-wrap: wrap; gap: 18px; padding: 18px; }
.tr-card { margin: 0; }
.tr-view { display: block; overflow: hidden; border: 1px solid #ccc; border-radius: 8px; background: #fff; }
.tr-frame { border: 0; transform-origin: 0 0; pointer-events: none; }
figcaption { margin-top: 6px; }
figcaption small { color: #666; }
</style>
