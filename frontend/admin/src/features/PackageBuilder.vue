<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { usd } from '@rootsquares/ui/mock/pricing'
import { buildGraph, stepOf, switchOff, switchOn, type PkgNode } from './packageGraph'

// The hierarchy of a custom package in five views of the same data (W19-R25, from the design project's `Package Map.html` and `Package Views.html`):
// Map (left to right), Hierarchy (top to bottom), Steps (what can be switched on together) and Outline.
// Click a part to light its chain; double-click, or the switch in the Map's side panel, switches it on or off. Switching on brings what it needs,
// switching off takes what needs it (packageGraph.ts); the platform repeats the rules on save.
const props = defineProps<{ nodes: PkgNode[]; modelValue: string[]; guide?: number[] }>()
const emit = defineEmits<{ 'update:modelValue': [v: string[]] }>()
const { t } = useI18n()

const VIEWS = ['map', 'steps', 'hierarchy', 'outline'] as const
type View = (typeof VIEWS)[number]
const view = ref<View>('map')
const guideLine = (step: number) => (props.guide?.[step] ? t('own.custom.pb.from', { amount: usd(props.guide[step]!) }) : '')
const g = computed(() => buildGraph(props.nodes))
const info = computed(() => g.value.info)
const ids = computed(() => g.value.ids)
const on = computed(() => new Set(props.modelValue))
const sel = ref<string | null>(null)
watch(ids, (v) => { if (!sel.value || !info.value[sel.value]) sel.value = v.includes('tickets') ? 'tickets' : (v[0] ?? null) }, { immediate: true })
const modOn = computed(() => props.nodes.filter((n) => !n.core && on.value.has(n.id)).length)
const modTotal = computed(() => props.nodes.filter((n) => !n.core).length)
const name = (id: string) => info.value[id]?.name ?? id
const names = (list: Iterable<string>) => [...list].map(name).join(', ')
const sub = (id: string) => { const n = info.value[id]!; return n.direct.length ? t('own.custom.pb.waits', { list: names(n.direct) }) : n.core ? t('own.custom.pb.alone') : '' }
const steps = [0, 1, 2, 3, 4]
const inStep = (s: number) => ids.value.filter((i) => stepOf(g.value, i) === s)
function cls(id: string) {
  const s = sel.value ? info.value[sel.value] : undefined
  return { on: on.value.has(id), off: !on.value.has(id), core: !!info.value[id]?.core, sel: id === sel.value, up: !!s && s.deep.has(id), dn: !!s && s.all.has(id), dim: !!s && id !== sel.value && !s.deep.has(id) && !s.all.has(id) }
}

// ---- selecting and switching ----
const toastText = ref('')
let toastTimer: ReturnType<typeof setTimeout> | undefined
function toast(text: string) {
  toastText.value = text
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastText.value = '' }, 3200)
}
function toggle(id: string) {
  const next = new Set(on.value)
  if (next.has(id)) {
    const x = switchOff(g.value, next, id)
    toast(x.length ? t('own.custom.pb.offAlso', { name: name(id), list: names(x) }) : t('own.custom.pb.off', { name: name(id) }))
  } else {
    const x = switchOn(g.value, next, id)
    toast(x.length ? t('own.custom.pb.onAlso', { name: name(id), list: names(x) }) : t('own.custom.pb.on', { name: name(id) }))
  }
  emit('update:modelValue', ids.value.filter((i) => next.has(i)))
}
function pick(id: string) { sel.value = id }
const idOf = (e: Event) => (e.target as HTMLElement).closest<HTMLElement>('[data-id]')?.dataset.id
// One click: the tick box switches the part on or off; anywhere else on the part selects it and lights its chain.
function onClick(e: MouseEvent) {
  const id = idOf(e)
  if (!id) return
  pick(id)
  if ((e.target as HTMLElement).closest('.pb-ck')) toggle(id)
}
// Starting from nothing (or from everything) is common, so there are three shortcuts.
function setAll(kind: 'on' | 'off' | 'modulesOff') {
  const keep = kind === 'on' ? ids.value : kind === 'off' ? [] : props.nodes.filter((n) => n.core).map((n) => n.id)
  emit('update:modelValue', ids.value.filter((i) => keep.includes(i)))
  toast(t(`own.custom.pb.${kind}Done`))
}

// ---- the lines (Map and Hierarchy) are measured from the boxes on screen ----
const wrap = ref<HTMLElement | null>(null)
const edgeSvg = ref('')
const edgeSize = ref({ w: 0, h: 0 })
function drawEdges() {
  const el = wrap.value
  if (!el || (view.value !== 'map' && view.value !== 'hierarchy')) { edgeSvg.value = ''; return }
  const r = el.getBoundingClientRect()
  const box = (id: string) => el.querySelector(`[data-id="${id}"]`)?.getBoundingClientRect()
  const s = sel.value ? info.value[sel.value] : undefined
  const up = new Set(s ? [sel.value!, ...s.deep] : [])
  const down = new Set(s ? [sel.value!, ...s.all] : [])
  const lo: string[] = []
  const hi: string[] = []
  const map = view.value === 'map'
  for (const id of ids.value) {
    for (const n of info.value[id]!.direct) {
      const a = box(n)
      const b = box(id)
      if (!a || !b) continue
      const chain = !!s && ((up.has(id) && up.has(n)) || (down.has(id) && down.has(n)))
      const live = on.value.has(n) && on.value.has(id)
      let x1: number, y1: number, x2: number, y2: number, d: string
      if (map) {
        x1 = a.right - r.left; y1 = a.top + a.height / 2 - r.top; x2 = b.left - r.left; y2 = b.top + b.height / 2 - r.top
        const dx = Math.max(30, (x2 - x1) / 2)
        d = `M${x1} ${y1}C${x1 + dx} ${y1},${x2 - dx} ${y2},${x2} ${y2}`
      } else {
        x1 = a.left + a.width / 2 - r.left; y1 = a.bottom - r.top; x2 = b.left + b.width / 2 - r.left; y2 = b.top - r.top
        const m = (y1 + y2) / 2
        d = `M${x1} ${y1}C${x1} ${m},${x2} ${m},${x2} ${y2}`
      }
      const stroke = chain ? 'var(--color-brass)' : 'var(--color-text)'
      const opacity = chain ? 1 : s && !map ? 0.07 : live ? (map ? 0.22 : 0.2) : map ? 0.12 : 0.1
      const line = `<path d="${d}" fill="none" stroke="${stroke}" stroke-width="${chain ? 2.4 : 1}" ${live ? '' : 'stroke-dasharray="4 4"'} opacity="${opacity}"/>`
      const dot = map ? `<circle cx="${x2}" cy="${y2}" r="${chain ? 3.5 : 2}" fill="${stroke}" opacity="${chain ? 1 : 0.3}"/>` : ''
      ;(chain ? hi : lo).push(line + dot)
    }
  }
  edgeSize.value = { w: r.width, h: r.height }
  edgeSvg.value = lo.join('') + hi.join('')
}
const redraw = () => { void nextTick(drawEdges) }
let observer: ResizeObserver | undefined
watch([view, sel, () => props.modelValue, ids], redraw, { flush: 'post' })
watch(wrap, (el) => { observer?.disconnect(); if (el) observer?.observe(el); redraw() })
onMounted(() => {
  observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(redraw)
  if (wrap.value) observer?.observe(wrap.value)
  window.addEventListener('resize', redraw)
  void document.fonts?.ready.then(redraw)
  redraw()
})
onBeforeUnmount(() => { observer?.disconnect(); window.removeEventListener('resize', redraw); clearTimeout(toastTimer) })

// ---- the summary and the outline ----
const current = computed(() => (sel.value ? info.value[sel.value] : undefined))
const sequence = computed(() => (current.value ? [...current.value.deep, current.value.id].sort((a, b) => info.value[a]!.lv - info.value[b]!.lv || ids.value.indexOf(a) - ids.value.indexOf(b)) : []))
const needsFirst = computed(() => (current.value ? [...current.value.deep].sort((a, b) => info.value[a]!.lv - info.value[b]!.lv) : []))
const keptOnBy = computed(() => (current.value ? [...current.value.all] : []))
const offNeeds = computed(() => needsFirst.value.filter((x) => !on.value.has(x)))
const onUsers = computed(() => keptOnBy.value.filter((x) => on.value.has(x)))
const outline = computed(() => {
  const par = (id: string) => [...info.value[id]!.direct].sort((a, b) => info.value[b]!.lv - info.value[a]!.lv)[0] ?? null
  const kids = (p: string) => ids.value.filter((i) => par(i) === p)
  const rows: { id: string; d: number; extra: string[] }[] = []
  const walk = (p: string, d: number) => kids(p).forEach((i) => { rows.push({ id: i, d, extra: info.value[i]!.direct.filter((x) => x !== par(i)) }); walk(i, d + 1) })
  const roots = ids.value.filter((i) => !par(i)).sort((a, b) => info.value[b]!.all.size - info.value[a]!.all.size)
  roots.forEach((i) => { rows.push({ id: i, d: 0, extra: [] }); walk(i, 1) })
  return rows
})
</script>

<template>
  <div class="pb" data-testid="package-builder">
    <div class="pb-head">
    <div class="pb-bar">
      <div class="pb-seg" role="group" :aria-label="t('own.custom.pb.views')">
        <button v-for="v in VIEWS" :key="v" type="button" :class="{ on: view === v }" :aria-pressed="view === v" @click="view = v">{{ t(`own.custom.pb.view.${v}`) }}</button>
      </div>
      <b class="pb-count">{{ t('own.custom.pb.count', { n: modOn, total: modTotal }) }}</b>
      <span class="pb-bulk" role="group" :aria-label="t('own.custom.pb.bulk')"><button type="button" @click="setAll('on')">{{ t('own.custom.pb.allOn') }}</button><button type="button" @click="setAll('modulesOff')">{{ t('own.custom.pb.modulesOff') }}</button><button type="button" @click="setAll('off')">{{ t('own.custom.pb.allOff') }}</button></span>
      <span class="pb-hint">{{ t('own.custom.pb.hint') }}</span>
    </div>
    <div class="pb-lead"><b>{{ t(`own.custom.pb.info.${view}.title`) }}</b><p>{{ t(`own.custom.pb.info.${view}.text`) }}</p></div>
    <div class="pb-legend" aria-hidden="true">
      <span><i class="pb-lk" />{{ t('own.custom.pb.legendNeeds') }}</span><span><i class="pb-lk off" />{{ t('own.custom.pb.legendOff') }}</span><span><i class="pb-lk chain" />{{ t('own.custom.pb.legendChain') }}</span>
      <span><i class="pb-ck on" />{{ t('own.custom.pb.legendOn') }}</span><span><i class="pb-ck on core" />{{ t('own.custom.pb.legendCore') }}</span>
    </div>
    </div>

    <section class="pb-sum" aria-live="polite" data-testid="package-summary">
      <template v-if="current">
        <div class="pb-sum-head">
          <div class="pb-sum-id">
            <div class="pb-eyebrow">{{ t('own.custom.pb.stepOf', { n: stepOf(g, current.id) + 1, name: t(`own.custom.pb.step.${stepOf(g, current.id)}.name`) }) }}</div>
            <h4 class="pb-h">{{ current.name }}</h4>
            <p>{{ current.desc }}</p>
          </div>
          <button type="button" class="pb-sw" :class="{ on: on.has(current.id) }" :aria-pressed="on.has(current.id)" @click="toggle(current.id)">
            <span>{{ t(on.has(current.id) ? 'own.custom.pb.inPackage' : 'own.custom.pb.notInPackage') }}</span><span class="pb-tg" />
          </button>
        </div>
        <div v-if="on.has(current.id) && onUsers.length" class="pb-warn">{{ t('own.custom.pb.offWarn', { n: onUsers.length, list: names(onUsers) }) }}</div>
        <div v-if="!on.has(current.id) && offNeeds.length" class="pb-warn">{{ t('own.custom.pb.onWarn', { list: names(offNeeds) }) }}</div>
        <div class="pb-sum-cols">
          <div>
            <h5>{{ t('own.custom.pb.needsFirst', { n: needsFirst.length }) }}</h5>
            <template v-if="needsFirst.length"><button v-for="x in needsFirst" :key="x" type="button" class="pb-pill" :class="{ o: !on.has(x) }" @click="sel = x">{{ name(x) }}</button></template>
            <p v-else class="pb-none">{{ t('own.custom.pb.needsNothing') }}</p>
          </div>
          <div>
            <h5>{{ t('own.custom.pb.keptOnBy', { n: keptOnBy.length }) }}</h5>
            <template v-if="keptOnBy.length"><button v-for="x in keptOnBy" :key="x" type="button" class="pb-pill" :class="{ o: !on.has(x) }" @click="sel = x">{{ name(x) }}</button></template>
            <p v-else class="pb-none">{{ t('own.custom.pb.dependsNothing') }}</p>
          </div>
          <div>
            <h5>{{ t('own.custom.pb.sequence') }}</h5>
            <ol class="pb-seq"><li v-for="x in sequence" :key="x" :class="{ me: x === current.id }">{{ name(x) }}</li></ol>
          </div>
        </div>
      </template>
      <p v-else class="pb-none">{{ t('own.custom.pb.pick') }}</p>
    </section>

    <div class="pb-main">
      <div class="pb-scroll" @click="onClick">
        <!-- Map: five columns, left to right -->
        <div v-if="view === 'map'" ref="wrap" class="pb-g">
          <svg class="pb-esv" :width="edgeSize.w" :height="edgeSize.h" aria-hidden="true" v-html="edgeSvg" />
          <div v-for="s in steps" :key="s" class="pb-col">
            <div class="pb-ch"><span>{{ s + 1 }} · {{ t(`own.custom.pb.step.${s}.name`) }}</span><small>{{ t(`own.custom.pb.step.${s}.text`) }}</small><small v-if="guideLine(s)" class="pb-gd">{{ guideLine(s) }}</small></div>
            <button v-for="i in inStep(s)" :key="i" type="button" class="pb-n" :class="cls(i)" :data-id="i" :aria-pressed="on.has(i)">
              <span class="pb-ck" /><b>{{ name(i) }}</b><small>{{ sub(i) }}</small>
            </button>
          </div>
        </div>

        <!-- Hierarchy (with lines) and Steps (without): one row per step -->
        <div v-else-if="view === 'hierarchy' || view === 'steps'" ref="wrap" class="pb-wv" :class="{ flat: view === 'steps' }">
          <svg v-if="view === 'hierarchy'" class="pb-esv" :width="edgeSize.w" :height="edgeSize.h" aria-hidden="true" v-html="edgeSvg" />
          <div v-for="s in steps" :key="s" class="pb-wave">
            <div class="pb-wh"><b>{{ t('own.custom.pb.stepN', { n: s + 1 }) }}</b><small>{{ t(`own.custom.pb.step.${s}.text`) }}</small><small v-if="guideLine(s)" class="pb-gd">{{ guideLine(s) }}</small></div>
            <div class="pb-chips">
              <button v-for="i in inStep(s)" :key="i" type="button" class="pb-n" :class="cls(i)" :data-id="i" :aria-pressed="on.has(i)">
                <span class="pb-ck" /><b>{{ name(i) }}</b><small>{{ sub(i) }}</small>
              </button>
            </div>
          </div>
        </div>

        <!-- Outline: each part under the last thing it waits for -->
        <div v-else class="pb-tr">
          <div v-for="r in outline" :key="r.id" class="pb-row" :class="{ sel: sel === r.id }" :style="{ '--d': r.d }" :data-id="r.id">
            <span class="pb-ck" :class="{ on: on.has(r.id), off: !on.has(r.id), core: info[r.id]!.core }" /><b>{{ name(r.id) }}</b>
            <span v-for="x in r.extra" :key="x" class="pb-tag">+ {{ name(x) }}</span>
            <span class="pb-ds">{{ info[r.id]!.desc }}</span>
          </div>
        </div>
      </div>

    </div>
    <div class="pb-toast" :class="{ on: !!toastText }" role="status">{{ toastText }}</div>
  </div>
</template>

<style scoped>
.pb { display: grid; gap: 10px; min-width: 0; }
.pb-head { display: grid; gap: 10px; padding: 12px 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--shape-surface); }
.pb-bar { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.pb-seg { display: inline-flex; border: 1px solid var(--color-border); border-radius: var(--shape-control); overflow: hidden; }
.pb-seg button { border: 0; background: none; padding: 7px 14px; font: inherit; font-size: 12.5px; cursor: pointer; color: var(--color-text-muted); }
.pb-seg button.on { background: var(--color-primary); color: var(--color-on-primary); }
.pb-count { font-weight: 600; font-size: var(--text-sm); }
.pb-bulk { display: inline-flex; gap: 6px; }
.pb-bulk button { border: 1px solid var(--color-border-strong, var(--color-border)); background: var(--color-surface); border-radius: var(--shape-control); min-height: 30px; padding: 0 14px; font: inherit; font-weight: 500; font-size: var(--text-xs); cursor: pointer; color: var(--color-text); }
.pb-bulk button:hover { border-color: var(--color-text); }
.pb-ck { cursor: pointer; }
.pb-ck:before { content: ""; position: absolute; inset: -8px; }
.pb-hint { color: var(--color-text-muted); font-size: 12px; }
.pb-lead { display: flex; gap: 16px; align-items: baseline; flex-wrap: wrap; }
.pb-lead b { font: 500 22px var(--font-display); }
.pb-lead p { margin: 0; color: var(--color-text-muted); max-width: 70ch; font-size: var(--text-sm); }
.pb-legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 11.5px; color: var(--color-text-muted); align-items: center; }
.pb-lk { display: inline-block; width: 22px; height: 0; border-top: 1.5px solid var(--color-text); vertical-align: middle; margin-right: 6px; }
.pb-lk.off { border-top: 1.5px dashed var(--color-text-muted); }
.pb-lk.chain { border-top: 2.5px solid var(--color-brass); }
.pb-legend .pb-ck { position: relative; display: inline-block; vertical-align: middle; margin-right: 6px; left: auto; top: auto; }
.pb-main { display: grid; grid-template-columns: minmax(0, 1fr); border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-bg); min-width: 0; }
.pb-scroll { overflow: auto; position: relative; padding: 16px 12px 24px; max-height: 72vh; }

/* the summary of the selected part: one block above every view, fixed while the page scrolls */
.pb-sum { position: sticky; top: 64px; z-index: 4; display: grid; gap: 10px; padding: 12px 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-top: 3px solid var(--color-brass); border-radius: var(--shape-surface); box-shadow: 0 6px 14px -10px rgb(0 0 0 / 0.35); max-height: 46vh; overflow: auto; }
.pb-sum-head { display: flex; gap: 16px; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; }
.pb-sum-id { display: grid; gap: 2px; min-width: 0; flex: 1 1 320px; }
.pb-sum p { margin: 0; color: var(--color-text-muted); font-size: var(--text-sm); }
.pb-sum-cols { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px 24px; }
.pb-sum .pb-sw { width: auto; min-width: 210px; }

/* shared box and check */
.pb-ck { position: absolute; left: 10px; top: 11px; width: 16px; height: 16px; border-radius: 4px; border: 1.5px solid var(--color-text-muted); flex: none; }
.pb-ck.on { background: var(--color-primary); border-color: var(--color-primary); }
.pb-ck.on:after { content: ""; position: absolute; left: 2px; top: 3px; width: 8px; height: 4px; border-left: 2px solid var(--color-surface); border-bottom: 2px solid var(--color-surface); rotate: -45deg; }
.pb-ck.core.on { background: var(--color-brass); border-color: var(--color-brass); }
.pb-ck.off { border-style: dashed; }
.pb-n { position: relative; text-align: left; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--shape-inner); padding: 8px 12px 8px 34px; cursor: pointer; min-height: 44px; min-width: 150px; transition: 0.15s; font: inherit; color: inherit; }
.pb-n:hover { border-color: var(--color-text); }
.pb-n b { display: block; font-weight: 600; font-size: 12.5px; }
.pb-n small { display: block; color: var(--color-text-muted); font-size: 11px; }
.pb-n.on .pb-ck { background: var(--color-primary); border-color: var(--color-primary); }
.pb-n.on .pb-ck:after { content: ""; position: absolute; left: 2px; top: 3px; width: 8px; height: 4px; border-left: 2px solid var(--color-surface); border-bottom: 2px solid var(--color-surface); rotate: -45deg; }
.pb-n.on.core .pb-ck { background: var(--color-brass); border-color: var(--color-brass); }
.pb-n.off { background: transparent; border-style: dashed; }
.pb-n.off b { color: var(--color-text-muted); }
.pb-n.sel { border-color: var(--color-brass); box-shadow: 0 0 0 2px color-mix(in srgb, var(--color-brass) 35%, transparent); }
.pb-n.up, .pb-n.dn { border-color: var(--color-brass); }
.pb-n.dim { opacity: 0.35; }
.pb-esv { position: absolute; inset: 0; pointer-events: none; overflow: visible; z-index: 0; }

/* map */
.pb-g { position: relative; display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0 28px; min-width: 840px; }
.pb-col .pb-n { min-width: 0; }
.pb-col { display: flex; flex-direction: column; gap: 8px; position: relative; z-index: 1; }
.pb-ch { font: 500 9.5px var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-brass-text); padding-bottom: 6px; border-bottom: 1px solid var(--color-border); margin-bottom: 4px; }
.pb-ch small { display: block; letter-spacing: 0; text-transform: none; color: var(--color-text-muted); font-size: 11px; margin-top: 2px; font-weight: 400; }
.pb-h { font: 500 24px/1.05 var(--font-display); margin: 0; }
.pb-eyebrow { font-size: 11px; color: var(--color-brass-text); letter-spacing: 0.14em; text-transform: uppercase; font-weight: 500; margin-bottom: 4px; }
.pb-sum h5 { font: 500 9.5px var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-text-muted); margin: 0 0 6px; }
.pb-pill { display: inline-flex; align-items: center; border: 1px solid var(--color-border); border-radius: var(--shape-control); padding: 3px 10px; font: inherit; font-size: 12px; margin: 0 6px 6px 0; cursor: pointer; background: var(--color-bg); color: var(--color-text); }
.pb-pill:hover { border-color: var(--color-brass); }
.pb-pill.o { border-style: dashed; color: var(--color-text-muted); }
.pb-seq { margin: 0; padding: 0; list-style: none; counter-reset: s; display: flex; flex-wrap: wrap; gap: 6px; }
.pb-seq li { counter-increment: s; display: inline-flex; gap: 6px; align-items: center; border: 1px solid var(--color-border); border-radius: var(--shape-control); padding: 2px 10px 2px 4px; font-size: 12px; background: var(--color-bg); }
.pb-seq li:before { content: counter(s); width: 18px; height: 18px; border-radius: 50%; background: var(--color-surface); border: 1px solid var(--color-brass); font-size: 10.5px; display: grid; place-items: center; color: var(--color-brass-text); font-weight: 600; }
.pb-seq li.me { font-weight: 600; border-color: var(--color-brass); }
.pb-sw { display: flex; align-items: center; justify-content: space-between; gap: 10px; border: 1px solid var(--color-border); border-radius: var(--shape-inner); padding: 10px 12px; background: var(--color-bg); cursor: pointer; width: 100%; font: inherit; color: inherit; text-align: left; }
.pb-sw:hover { border-color: var(--color-text); }
.pb-gd { color: var(--color-brass-text); font-weight: 500; }
.pb-tg { width: 34px; height: 20px; border-radius: var(--shape-control); background: var(--color-border); position: relative; flex: none; }
.pb-tg:after { content: ""; position: absolute; left: 2px; top: 2px; width: 16px; height: 16px; border-radius: 50%; background: var(--color-surface); transition: 0.15s; }
.pb-sw.on .pb-tg { background: var(--color-primary); }
.pb-sw.on .pb-tg:after { left: 16px; }
.pb-warn { background: color-mix(in srgb, var(--color-brass) 14%, var(--color-surface)); border: 1px solid color-mix(in srgb, var(--color-brass) 50%, transparent); border-radius: var(--shape-inner); padding: 9px 11px; font-size: 12px; color: var(--color-text); }
.pb-none { font-size: 12px; }

/* hierarchy and steps */
.pb-wv { position: relative; display: flex; flex-direction: column; }
.pb-wave { display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: 12px; padding: 0 0 46px; position: relative; z-index: 1; }
.pb-wave:last-child { padding-bottom: 0; }
.flat .pb-wave { padding: 16px 0; border-top: 1px solid var(--color-border); }
.flat .pb-wave:first-of-type { border-top: 0; }
.pb-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; align-content: flex-start; }
.flat .pb-chips { justify-content: flex-start; }
.pb-wh { padding-top: 8px; }
.pb-wh:before { content: ""; display: block; width: 28px; height: 1px; background: var(--color-brass); margin-bottom: 8px; }
.pb-wh b { display: block; font: 500 22px/1 var(--font-display); color: var(--color-brass-text); }
.pb-wh small { color: var(--color-text-muted); font-size: 11.5px; }

/* outline */
.pb-tr { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--shape-surface); padding: 10px 0; }
.pb-row { display: flex; align-items: center; gap: 10px; padding: 5px 16px 5px calc(16px + var(--d) * 28px); position: relative; cursor: pointer; }
.pb-row:hover { background: var(--color-bg); }
.pb-row:before { content: ""; position: absolute; left: calc(16px + var(--d) * 28px - 16px); top: 0; bottom: 50%; width: 12px; border-left: 1px solid var(--color-brass); border-bottom: 1px solid var(--color-brass); }
.pb-row[style*="--d: 0"]:before { display: none; }
.pb-row .pb-ck { position: relative; left: auto; top: auto; }
.pb-row b { font-weight: 600; font-size: 12.5px; }
.pb-tag { font-size: 11px; border: 1px solid var(--color-border); border-radius: var(--shape-control); padding: 1px 8px; color: var(--color-text-muted); background: var(--color-bg); }
.pb-ds { color: var(--color-text-muted); font-size: 11.5px; margin-left: auto; max-width: 44%; text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pb-row.sel { background: color-mix(in srgb, var(--color-brass) 14%, var(--color-surface)); }

.pb-toast { position: fixed; left: 24px; bottom: 20px; background: var(--color-primary); color: var(--color-on-primary); padding: 10px 14px; border-radius: var(--shape-surface); font-size: 12.5px; max-width: 520px; opacity: 0; translate: 0 8px; transition: 0.2s; pointer-events: none; z-index: 50; }
.pb-toast.on { opacity: 1; translate: 0; }
@media (max-width: 900px) { .pb-sum { position: static; max-height: none; } .pb-sum-cols { grid-template-columns: minmax(0, 1fr); } .pb-wave { grid-template-columns: 1fr; gap: 8px; } }
</style>
