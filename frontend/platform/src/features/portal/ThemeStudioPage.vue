<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { onBeforeRouteLeave } from 'vue-router'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { platform, type ThemeLook } from '@/services/platform'
import { ALL_THEMES, THEMES } from '@rootsquares/ui/themes'
import { THEME_COLORS } from '@/themes/colors'
import { STARTING_LOOKS } from '@/themes/startingLooks'
import ThemeComingList from '@/features/platform/ThemeComingList.vue'
import ThemePreviewPane from '@/features/platform/ThemePreviewPane.vue'
import { SHELL_FILTERS, useThemeFilter } from '@/features/platform/themeFilter'
import { errorText } from '@/features/platform/errorText'
import ThemeDraftPanel from './ThemeDraftPanel.vue'
import ThemeLookCard from './ThemeLookCard.vue'
import ThemeSeasonsPanel from './ThemeSeasonsPanel.vue'
import type { LookState } from './lookState'
import { useSquare } from './squareContext'

// The Theme Studio (W19-R3, route /squares/:id/theme/studio, outside the portal shell; the Theme page itself, SquareThemePage.vue, shows the current look and the way in). Laid out as the user's Theme Studio design (before that Theme Redesign, W18-R30): the studio fills the window and does not scroll. The preview takes the
// space above, scaled to fit; the tabs (Theme, Looks, Colours, Fonts, Shapes, Feel, Spinners) sit in a tray under it, a rail that scrolls sideways and that "Browse all" lifts into
// a wrapped grid. Share draft and Seasonal looks are in a drawer on the right. Save look stores the picked theme (PUT /squares/:id/theme) and the own look (the same call with
// `overrides`) together. The logos are on Settings (SquareLogos.vue, W10-R17). Themes that are not offered yet are listed under 'Coming up' (W10-R8; not in the design, see MISSING.md).
const { t } = useI18n()
const { push } = useToast()
const { sq, set } = useSquare()
const { q: themeQ, shell: themeShell, filtered: themesShown, counts: themeCounts, coming: themesComing } = useThemeFilter()
const swatches = (id: string) => { const c = THEME_COLORS[id]?.light; return c ? [c.bg, c.ink, c.accent] : [] }

type Tab = 'theme' | 'looks' | 'colours' | 'fonts' | 'shapes' | 'feel' | 'spinners'
const tab = ref<Tab>('theme')

const picked = ref('')
watch(() => sq.value?.theme_id, (id) => { if (id && !picked.value) picked.value = id }, { immediate: true })
const current = computed(() => ALL_THEMES.find((x) => x.id === sq.value?.theme_id))
const sel = computed(() => ALL_THEMES.find((x) => x.id === picked.value) ?? current.value)
const retired = computed(() => !!current.value && !THEMES.some((x) => x.id === current.value!.id)) // the square's theme is no longer offered (W18-R25)
const themeDirty = computed(() => !!sq.value && picked.value !== sq.value.theme_id)
const busy = ref(false)
const themeError = ref('')
const appliedName = ref('')
function pick(id: string) { picked.value = id; appliedName.value = '' }
async function applyTheme() {
  if (!sq.value || !themeDirty.value) return
  set(await platform.setSquareTheme(sq.value.id, picked.value))
  appliedName.value = sel.value?.name ?? picked.value
}

const look = ref<ThemeLook | null>(null) // the draft of the own look, shown in both previews (W18-R19)
const lookState = ref<LookState>({ dirty: false, hasAny: false, hasSaved: false, busy: false, allowed: false, colourName: '', fontName: '', shapeName: '', feelName: '', kept: 0 })
const lookCard = ref<InstanceType<typeof ThemeLookCard> | null>(null)
const unsaved = computed(() => themeDirty.value || lookState.value.dirty)

// One Save look for the whole page: the theme first, then the colours, fonts, shapes, feel and spinners (the card keeps its own error and done lines).
async function saveAll() {
  busy.value = true
  themeError.value = ''
  appliedName.value = ''
  try {
    await applyTheme()
    if (lookState.value.dirty) await lookCard.value?.saveLook()
  } catch (e) { themeError.value = errorText(t, e) } finally { busy.value = false }
}
// Discard changes (TS-05): the theme and everything in the tabs go back to what is saved; the preview's own switches too
function discardChanges() {
  if (current.value) picked.value = current.value.id
  appliedName.value = ''
  themeError.value = ''
  lookCard.value?.discard()
  compare.value = 'changes'
  modePick.value = null
}

// Leaving with unsaved changes (W19-R15): a way out of the studio (back link, the browser's back button, a menu) asks first; closing the tab gets the browser's own warning.
const leaveOpen = ref(false)
let leaveAnswer: ((ok: boolean) => void) | null = null
onBeforeRouteLeave(() => {
  if (!unsaved.value) return true
  leaveOpen.value = true
  return new Promise<boolean>((resolve) => { leaveAnswer = resolve })
})
function answerLeave(ok: boolean) { leaveOpen.value = false; leaveAnswer?.(ok); leaveAnswer = null }
function warnUnload(e: BeforeUnloadEvent) { if (unsaved.value) e.preventDefault() }

// Before and after (W18-R50): while there are unsaved changes the preview can show the live site (the saved theme and look) instead of the changes.
const compare = ref<'changes' | 'live'>('changes')
const savedLook = computed<ThemeLook | null>(() => {
  const o = sq.value?.theme_overrides
  return o && (o.colors || o.colors_dark || o.fonts || o.shape || o.feel || o.type) ? { colors: o.colors ? { ...o.colors } : null, colors_dark: o.colors_dark ? { ...o.colors_dark } : null, fonts: o.fonts ?? null, shape: o.shape ? { ...o.shape } : null, feel: o.feel ? { ...o.feel } : null, type: o.type ? JSON.parse(JSON.stringify(o.type)) : null } : null
})
const showLive = computed(() => compare.value === 'live' && unsaved.value)
const pvTheme = computed(() => (showLive.value && current.value ? current.value : sel.value))
const pvLook = computed(() => (showLive.value ? savedLook.value : look.value))
watch(unsaved, (u) => { if (!u) compare.value = 'changes' })
// What was said about the last save is no longer true once something changes again (TS-08)
watch(unsaved, (u) => { if (u) { appliedName.value = ''; themeError.value = '' } })

// The preview's own Light / Dark switch (W18-R31); it changes only what the preview shows. It starts as the look starts (the Feel tab's default mode, else the theme's own) and follows it
// until it is pressed, so the pressed chip and the picture always agree (TS-02).
const modePick = ref<'light' | 'dark' | null>(null)
const startMode = computed<'light' | 'dark'>(() => {
  const m = pvLook.value?.feel?.mode
  if (m === 'dark' || m === 'light') return m
  if (m === 'system' && typeof matchMedia === 'function') return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  return pvTheme.value?.mode === 'dark' ? 'dark' : 'light'
})
const mode = computed<'light' | 'dark'>({ get: () => modePick.value ?? startMode.value, set: (v) => { modePick.value = v } })
// A theme picked in quick succession loads the preview once, not once per click (TS-16)
const pvThemeShown = ref(pvTheme.value)
let pvTimer = 0
watch(pvTheme, (v) => { window.clearTimeout(pvTimer); pvTimer = window.setTimeout(() => { pvThemeShown.value = v }, 300) })
const device = ref<'desktop' | 'tablet' | 'phone'>('desktop')
// The preview is a picture until it is clicked; then it is the real site (scroll, click) until Esc or a click outside (the full preview dialog of the old page is not needed here).
const explore = ref(false)
function outside(e: PointerEvent) { if (explore.value && !(e.target as HTMLElement | null)?.closest('.tt-pv')) explore.value = false }
function clearFilters() { themeQ.value = ''; themeShell.value = '' }

const tabs = computed<{ id: Tab; label: string; value: string }[]>(() => [
  { id: 'theme', label: t('portal.theme.tabTheme'), value: sel.value?.name ?? '' },
  { id: 'looks', label: t('portal.theme.tabLooks'), value: t('portal.theme.look.startsCount', { n: STARTING_LOOKS.length }) },
  { id: 'colours', label: t('portal.theme.tabColours'), value: lookState.value.colourName },
  { id: 'fonts', label: t('portal.theme.tabFonts'), value: lookState.value.fontName },
  { id: 'shapes', label: t('portal.theme.tabShapes'), value: lookState.value.shapeName },
  { id: 'feel', label: t('portal.theme.tabFeel'), value: lookState.value.feelName },
  { id: 'spinners', label: t('portal.theme.tabSpinners'), value: t('portal.theme.look.spinnersKept', { n: lookState.value.kept }) },
])

// The studio (W19-R3): the tray is a rail until "Browse all" lifts it; the preview is scaled to the height the well has (measured, so no page scroll); the drawer holds the draft and the seasons.
const trayOpen = true // the customisations stand beside the preview, always open (W19-R9)
const drawer = ref<'' | 'draft' | 'seasons'>('')
const well = ref<HTMLElement | null>(null)
const wellH = ref(0)
let ro: ResizeObserver | null = null
const pvMax = computed(() => (wellH.value > 120 ? wellH.value - 24 - 30 - 2 : 0)) // the frame, its address bar (about 30 px) and the well's 12 px padding all round stay inside the well
const lookArgs = () => lookCard.value?.current() ?? null
function fromDrawer(l: Partial<ThemeLook>, themeId: string | null) { lookCard.value?.load(l); if (themeId) pick(themeId); drawer.value = ''; push(t('portal.theme.studio.loaded'), 'success') }
// The drawer is a dialog (TS-06): focus moves into it when it opens, Tab stays inside it, focus goes back to what opened it when it closes; its panels start fresh each time (TS-09).
const rootEl = ref<HTMLElement | null>(null)
const drawerEl = ref<HTMLElement | null>(null)
const drawerKey = ref(0)
let drawerOpener: HTMLElement | null = null
watch(drawer, async (d, was) => {
  if (d && !was) { drawerKey.value += 1; drawerOpener = document.activeElement as HTMLElement | null; await nextTick(); drawerEl.value?.querySelector<HTMLElement>('button')?.focus() }
  else if (!d && was) { drawerOpener?.focus?.(); drawerOpener = null }
})
function trapTab(e: KeyboardEvent) {
  const all = [...(drawerEl.value?.querySelectorAll<HTMLElement>('button, input, a[href], select, textarea') ?? [])].filter((x) => !(x as HTMLButtonElement).disabled && x.offsetParent !== null)
  if (!all.length) return
  const first = all[0]!, last = all[all.length - 1]!
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
}
const narrow = ref(false) // the phone and tablet layout: the preview above the tabs, so a button carries the way between them (TS-04)
const stageEl = ref<HTMLElement | null>(null)
const trayEl = ref<HTMLElement | null>(null)
const stageSeen = ref(true)
const touchy = typeof matchMedia === 'function' && matchMedia('(pointer: coarse)').matches // a touch screen has no Esc key (TS-18)
let mql: MediaQueryList | null = null
let io: IntersectionObserver | null = null
const onMql = () => { narrow.value = !!mql?.matches }
function fabGo() { (stageSeen.value ? trayEl.value : stageEl.value)?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }
const tabIds: Tab[] = ['theme', 'looks', 'colours', 'fonts', 'shapes', 'feel', 'spinners']
function tabKey(e: KeyboardEvent) { // arrow keys, Home and End move between the tabs (TS-14)
  const i = tabIds.indexOf(tab.value)
  const next = e.key === 'ArrowRight' ? (i + 1) % tabIds.length : e.key === 'ArrowLeft' ? (i + tabIds.length - 1) % tabIds.length : e.key === 'Home' ? 0 : e.key === 'End' ? tabIds.length - 1 : -1
  if (next < 0) return
  e.preventDefault()
  tab.value = tabIds[next]!
  void nextTick(() => document.getElementById(`tt-tab-${tab.value}`)?.focus())
}
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') { if (explore.value) explore.value = false; else if (drawer.value) drawer.value = ''; return }
  if (e.key === 'Tab' && drawer.value) trapTab(e)
}
onMounted(() => {
  if (typeof matchMedia === 'function') { mql = matchMedia('(max-width: 900px)'); onMql(); mql.addEventListener('change', onMql) }
  if (stageEl.value && rootEl.value && typeof IntersectionObserver !== 'undefined') { io = new IntersectionObserver(([en]) => { stageSeen.value = !!en?.isIntersecting }, { root: rootEl.value, threshold: 0.35 }); io.observe(stageEl.value) }
  if (well.value && typeof ResizeObserver !== 'undefined') { ro = new ResizeObserver(([en]) => { wellH.value = Math.round(en!.contentRect.height) }); ro.observe(well.value) }
  window.addEventListener('keydown', onKey)
  window.addEventListener('pointerdown', outside)
  window.addEventListener('beforeunload', warnUnload)
})
onBeforeUnmount(() => { io?.disconnect(); mql?.removeEventListener('change', onMql); window.clearTimeout(pvTimer); ro?.disconnect(); window.removeEventListener('keydown', onKey); window.removeEventListener('pointerdown', outside); window.removeEventListener('beforeunload', warnUnload) })
</script>

<template>
  <div v-if="sq" ref="rootEl" class="tt-root"><div class="tp tt">
    <div class="tt-head">
      <AppButton :to="`/squares/${sq.id}/theme`" class="tt-back" variant="secondary" size="sm" icon="chevron-left">{{ t('portal.theme.studio.back') }}</AppButton>
      <div class="tt-title"><h1 class="tt-h1">{{ t('portal.theme.studio.title') }}</h1><span class="bs-mute tt-sub">{{ sq.name }}</span></div>
      <span class="tt-sp" />
      <span v-if="unsaved" class="tt-dirty" role="status">{{ t('portal.theme.unsaved') }}</span>
      <AppButton v-if="unsaved" icon="undo" variant="secondary" :disabled="busy" @click="discardChanges">{{ t('portal.theme.discard') }}</AppButton>
      <AppButton icon="calendar" variant="secondary" @click="drawer = 'seasons'">{{ t('portal.theme.seasonsBtn') }}</AppButton>
      <AppButton icon="link" variant="secondary" @click="drawer = 'draft'">{{ t('portal.theme.shareBtn') }}</AppButton>
      <AppButton icon="check" :loading="busy" :disabled="!unsaved || (!themeDirty && !lookState.allowed)" @click="saveAll">{{ t('portal.theme.look.save') }}</AppButton>
    </div>
    <AppAlert v-if="retired && current" tone="info">{{ t('portal.theme.retired', { theme: current.name }) }}</AppAlert>
    <AppAlert v-if="appliedName" tone="success" :title="t('portal.theme.appliedTitle', { theme: appliedName })">{{ t('portal.theme.appliedBody') }}</AppAlert>
    <AppAlert v-if="themeError" tone="danger">{{ themeError }}</AppAlert>

    <div class="tt-body">
    <section ref="trayEl" class="tt-tray" :class="{ 'tt-tray--open': trayOpen }" :aria-label="t('portal.theme.title')">
      <nav class="tt-tabs" role="tablist" :aria-label="t('portal.theme.title')">
        <button v-for="x in tabs" :id="`tt-tab-${x.id}`" :key="x.id" type="button" role="tab" :aria-selected="tab === x.id" aria-controls="tt-panel" :tabindex="tab === x.id ? 0 : -1" @click="tab = x.id" @keydown="tabKey">{{ x.label }}<small>{{ x.value }}</small></button>
      </nav>
      <div id="tt-panel" class="tt-pane" role="tabpanel" :aria-labelledby="`tt-tab-${tab}`">
        <section class="tt-sec" :hidden="tab !== 'theme'">
          <p class="bs-mute tt-lede">{{ t('portal.theme.tabThemeLede') }}</p>
          <div class="tt-tools">
            <div class="rs-field tt-q">
              <label class="rs-label" for="tp-q" style="position: absolute; left: -9999px">{{ t('portal.theme.searchLabel') }}</label>
              <input id="tp-q" v-model="themeQ" class="rs-input" type="search" :placeholder="t('themes.search')" />
            </div>
            <div class="tp-chips" role="group" :aria-label="t('portal.theme.layoutLabel')">
              <button v-for="f in SHELL_FILTERS" :key="f.id" type="button" :aria-pressed="themeShell === f.id" @click="themeShell = f.id">{{ f.label }}<small>{{ themeCounts[f.id] }}</small></button>
            </div>
            <span class="bs-mute tt-count" role="status">{{ t('themes.count', { n: themesShown.length }, themesShown.length) }}</span>
          </div>
          <div class="tt-themes" role="group" :aria-label="t('portal.theme.listLabel')">
            <button v-for="th in themesShown" :key="th.id" type="button" class="tt-th" :aria-pressed="th.id === picked" @click="pick(th.id)">
              <span class="tt-sw"><i v-for="c in swatches(th.id)" :key="c" :style="{ background: c }" /></span>
              <span class="tt-txt">
                <b>{{ th.name }}<span v-if="th.id === sq.theme_id" class="rs-chip rs-chip--info">{{ t('portal.theme.inUse') }}</span></b>
                <small>{{ th.shellLabel }} · {{ th.look }}</small><small>{{ th.colour }}</small>
              </span>
            </button>
            <div v-if="!themesShown.length" class="tp-empty"><b>{{ t('portal.theme.noMatch') }}</b><span class="bs-mute">{{ t('portal.theme.noMatchBody') }}</span><AppButton icon="trash" variant="secondary" size="sm" @click="clearFilters">{{ t('portal.theme.clear') }}</AppButton></div>
          </div>
          <ThemeComingList v-if="trayOpen" :themes="themesComing" />
        </section>

        <section class="tt-sec">
          <ThemeLookCard ref="lookCard" :theme-id="picked || sq.theme_id" :section="tab" @preview="(v) => (look = v)" @state="(s) => (lookState = s)" @mode="(m) => (mode = m)" />
        </section>
      </div>
    </section>

    <div ref="stageEl" class="tt-stage">
      <div v-if="sel" class="tt-sbar">
        <span class="tt-name"><b>{{ sel.name }}</b><small class="bs-mute">{{ sel.shellLabel }} · {{ sel.colour }} · {{ sel.display }} / {{ sel.body }}</small></span>
        <span v-if="sel.id === sq.theme_id" class="rs-chip rs-chip--info">{{ t('portal.theme.inUse') }}</span>
        <span class="tt-sp" />
        <span v-if="unsaved" class="tp-chips" role="group" :aria-label="t('portal.theme.compare')">
          <button type="button" :aria-pressed="compare === 'changes'" @click="compare = 'changes'">{{ t('portal.theme.compareChanges') }}</button>
          <button type="button" :aria-pressed="compare === 'live'" @click="compare = 'live'">{{ t('portal.theme.compareLive') }}</button>
        </span>
        <span class="tp-chips" role="group" :aria-label="t('portal.theme.mode')">
          <button type="button" :aria-pressed="mode === 'light'" @click="mode = 'light'">{{ t('portal.theme.light') }}</button>
          <button type="button" :aria-pressed="mode === 'dark'" @click="mode = 'dark'">{{ t('portal.theme.dark') }}</button>
        </span>
        <span class="tp-chips" role="group" :aria-label="t('portal.theme.device')">
          <button type="button" :aria-pressed="device === 'desktop'" @click="device = 'desktop'">{{ t('portal.theme.desktop') }}</button>
          <button type="button" :aria-pressed="device === 'tablet'" @click="device = 'tablet'">{{ t('portal.theme.tablet') }}</button>
          <button type="button" :aria-pressed="device === 'phone'" @click="device = 'phone'">{{ t('portal.theme.phone') }}</button>
        </span>
      </div>
      <div ref="well" class="tt-well">
        <div v-if="sel" class="tt-pv" :class="{ 'tt-pv--on': explore }" :role="explore ? undefined : 'button'" :tabindex="explore ? undefined : 0" :aria-label="explore ? undefined : t('portal.theme.studio.try')" @click="explore = true" @keydown.enter.prevent="explore = true" @keydown.space.prevent="explore = true">
          <ThemePreviewPane :theme="pvThemeShown!" :name="sq.name" :sketch-zoom="1.5" :look="pvLook" :mode="mode" :device="device" :max-height="pvMax" grow :interactive="explore" />
          <span class="tp-zoom-hint"><AppIcon name="eye" :size="14" />{{ t(explore ? (touchy ? 'portal.theme.studio.stopTouch' : 'portal.theme.studio.stop') : 'portal.theme.studio.try') }}</span>
        </div>
      </div>
    </div>
    </div>

    <ConfirmDialog v-if="leaveOpen" :title="t('portal.theme.studio.leaveTitle')" :body="t('portal.theme.studio.leaveBody')" :verb="t('portal.theme.studio.leaveVerb')" icon="out" @cancel="answerLeave(false)" @confirm="answerLeave(true)" />

    <button v-if="narrow && !drawer" type="button" class="tt-fab" @click="fabGo"><AppIcon :name="stageSeen ? 'move-down' : 'eye'" :size="16" />{{ stageSeen ? t('portal.theme.fabEdit') : t('portal.theme.fabPreview') }}</button>
    <div class="tt-scrim" :class="{ 'tt-scrim--on': !!drawer }" @click="drawer = ''" />
    <aside ref="drawerEl" class="tt-drawer" :class="{ 'tt-drawer--on': !!drawer }" :aria-hidden="!drawer" :inert="!drawer" role="dialog" :aria-label="drawer === 'seasons' ? t('portal.theme.seasonsBtn') : t('portal.theme.shareBtn')">
      <div class="tt-dh">
        <div class="tp-chips" role="tablist">
          <button type="button" role="tab" :aria-pressed="drawer === 'draft'" @click="drawer = 'draft'">{{ t('portal.theme.shareBtn') }}</button>
          <button type="button" role="tab" :aria-pressed="drawer === 'seasons'" @click="drawer = 'seasons'">{{ t('portal.theme.seasonsBtn') }}</button>
        </div>
        <span class="tt-sp" />
        <AppButton icon="x" variant="ghost" @click="drawer = ''">{{ t('portal.theme.drawerClose') }}</AppButton>
      </div>
      <div class="tt-db">
        <div v-show="drawer !== 'seasons'"><ThemeDraftPanel :key="drawerKey" :allowed="lookState.allowed" :theme-id="picked || sq.theme_id" :get-look="lookArgs" :has-any="lookState.hasAny" @load="fromDrawer" /></div>
        <div v-show="drawer === 'seasons'"><ThemeSeasonsPanel :key="drawerKey" :allowed="lookState.allowed" :theme-id="picked || sq.theme_id" :get-look="lookArgs" :has-any="lookState.hasAny" @load="fromDrawer" /></div>
      </div>
    </aside>

  </div></div>
</template>

<style scoped>
/* The studio owns the whole window: no portal header or side bar around it (its route is outside the portal shell), so the full width and height are the studio's; on a phone it scrolls normally. */
.tt-root { position: fixed; inset: 0; z-index: 30; overflow: auto; background: var(--color-bg, var(--color-surface)); }
.tt { max-width: none; display: flex; flex-direction: column; gap: 10px; height: 100%; min-height: 560px; padding: 12px 18px 14px; box-sizing: border-box; }
.tt > * { flex: none; }
/* The top bar (W23-R42, from `Theme Studio Redesign.html`): a full-width bar with one divider line under it, the muted back link, the serif title with the square's name,
   and the buttons as capital pills (light outline for the quiet ones, the theme's dark fill for Save look). Nothing below the bar is changed. */
.tt-head { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 14px; margin: -12px -18px 4px; padding: 12px 20px; border-bottom: 1px solid var(--color-border); }
.tt-head :deep(.rs-btn.rs-btn) { padding: 0 16px; border-radius: var(--shape-control); font: 600 11px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; white-space: nowrap; }
.tt-head :deep(.rs-btn--secondary.rs-btn--secondary) { border-color: var(--color-border); background: var(--color-surface); color: var(--color-text); }
.tt-head :deep(.rs-btn--secondary.rs-btn--secondary:hover) { border-color: var(--color-brass); color: var(--color-brass-text); }
.tt-title { display: flex; align-items: baseline; gap: 10px; min-width: 0; }
.tt-h1 { margin: 0; font: 400 28px/1 var(--font-display, var(--font-sans)); }
.tt-sub { font-size: var(--text-sm); }
.tt-sp { flex: 1; }
/* The two- and three-way switches (Changes / Live, Light / Dark, Desktop / Tablet / Phone, and the tabs of the side panel) are one pill with the choices inside, as in the design (W23-R43). */
.tt-sbar .tp-chips, .tt-dh .tp-chips { flex-wrap: nowrap; gap: 2px; padding: 3px; overflow: visible; border-radius: var(--shape-control); background: var(--color-surface-sunken); }
.tt-sbar .tp-chips button, .tt-dh .tp-chips button { min-height: 30px; padding: 0 14px; border: 0; border-radius: var(--shape-control); background: none; color: var(--color-text-muted); font-size: var(--text-sm); font-weight: 500; white-space: nowrap; }
.tt-sbar .tp-chips button[aria-pressed=true], .tt-dh .tp-chips button[aria-pressed=true] { background: var(--color-primary); color: var(--color-on-primary); border: 0; box-shadow: none; font-weight: 600; }
.tt-dirty { color: var(--color-brass-text); font-size: var(--text-sm); font-weight: 600; }
.tt-stage { flex: 1 1 0; min-width: 0; min-height: 0; display: flex; flex-direction: column; gap: 8px; }
.tt-sbar { display: flex; align-items: center; flex-wrap: nowrap; gap: 8px 10px; } /* one line on a wide screen: the stage does not change height when Compare appears (TS-32) */
.tt-sbar .tp-chips { flex: none; }
.tt-name { display: grid; flex: 1 1 0; min-width: 0; }
.tt-name b, .tt-name small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tt-name b { font-weight: 500; font-size: var(--text-lg); }
.tt-name small { font-size: var(--text-xs); }
.tt-well { flex: 1 1 0; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr); place-items: center stretch; padding: 12px; box-sizing: border-box; overflow: hidden; border: 1px solid var(--color-border); border-radius: 16px; background: repeating-linear-gradient(45deg, var(--color-surface-sunken) 0 10px, var(--color-surface) 10px 20px); }
.tt-pv { position: relative; width: 100%; max-height: 100%; cursor: pointer; border-radius: 8px; }
.tt-pv:focus-visible { outline: 2px solid var(--color-brass); outline-offset: 3px; }
.tt-pv .tp-zoom-hint { position: absolute; inset-inline-end: 10px; inset-block-end: 10px; display: inline-flex; gap: 6px; align-items: center; padding: 6px 10px; border-radius: 99px; background: var(--color-surface-raised); color: var(--color-text); border: 1px solid var(--color-border-strong); box-shadow: var(--shadow-md); font-size: var(--text-xs); opacity: 0; transition: opacity var(--duration-fast); }
.tt-pv:hover .tp-zoom-hint, .tt-pv:focus-visible .tp-zoom-hint, .tt-pv--on .tp-zoom-hint { opacity: 1; }
.tt-pv--on { cursor: auto; outline: 2px solid var(--color-brass); outline-offset: 3px; }
.tt-pv--on .tp-zoom-hint { pointer-events: none; }
.tt-body { flex: 1 1 0; min-height: 0; display: flex; gap: 14px; }
.tt-tray { flex: 0 0 clamp(400px, 33vw, 620px); min-width: 0; display: flex; flex-direction: column; border: 1px solid var(--color-border); border-radius: 16px; background: var(--color-surface); }
.tt-tabs { display: flex; gap: 2px; align-items: stretch; padding: 0 10px; border-bottom: 1px solid var(--color-border); flex: none; flex-wrap: wrap; }
.tt-tabs button { display: grid; justify-items: start; gap: 1px; padding: 9px 12px; min-width: 0; border: 0; border-bottom: 2px solid transparent; margin-bottom: -1px; background: none; color: var(--color-text-muted); font: 600 0.7rem/1.2 var(--font-sans); letter-spacing: 0.15em; text-transform: uppercase; white-space: nowrap; cursor: pointer; }
.tt-tabs button small { font: 400 var(--text-xs) var(--font-sans); letter-spacing: 0; text-transform: none; max-width: 150px; white-space: normal; text-align: start; } /* the caption wraps, the name is never cut off (TS-11) */
.tt-tabs button:hover { color: var(--color-text); }
.tt-tabs button[aria-selected='true'] { color: var(--color-brass-text); border-bottom-color: var(--color-brass); }
.tt-tabs button:focus-visible { outline: 2px solid var(--color-focus, var(--color-primary)); outline-offset: -2px; }
.tt-tabs .tt-x { margin: auto 4px auto auto; padding: 5px 12px; border: 1px solid var(--color-border-strong); border-radius: 99px; background: var(--color-surface); color: var(--color-text); font: 600 var(--text-xs) var(--font-sans); letter-spacing: 0; text-transform: none; }
.tt-tabs .tt-x:hover { border-color: var(--color-brass); }
.tt-pane { flex: 1; min-height: 0; overflow: auto; padding: 14px 16px; display: grid; gap: 10px; align-content: start; }
.tt-sec { display: grid; gap: 10px; min-width: 0; }
.tt-sec[hidden] { display: none; }
.tt-lede { margin: 0; font-size: var(--text-sm); }
.tt-tools { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 12px; }
.tt-q { flex: 1 1 280px; min-width: 200px; max-width: 100%; } /* wide enough for the whole placeholder (TS-31) */
.tt-count { font-size: var(--text-xs); }
.tt-tools .tp-chips { flex-wrap: wrap; }
/* collapsed: one row that scrolls sideways; open: the tiles wrap and the pane scrolls up and down */
.tt-themes { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 150px), 1fr)); gap: 8px; padding: 2px; }
.tt-th { min-width: 0; align-self: start; display: grid; grid-template-rows: 22px 1fr; padding: 0; overflow: hidden; border: 1px solid var(--color-border-strong); border-radius: 12px; background: var(--color-surface); color: var(--color-text); text-align: start; font: inherit; cursor: pointer; }
.tt-th:hover { border-color: var(--color-brass); }
.tt-th[aria-pressed='true'] { border-color: var(--color-brass); box-shadow: 0 0 0 2px var(--color-brass-subtle), inset 0 0 0 1px var(--color-brass); }
.tt-sw { display: flex; }
.tt-sw i { flex: 1; }
.tt-sw i:first-child { flex: 2; }
.tt-txt { display: grid; gap: 1px; padding: 8px 10px 10px; min-width: 0; }
.tt-txt b { display: flex; justify-content: space-between; align-items: center; gap: 6px; font-size: var(--text-sm); font-weight: 500; }
.tt-txt small { display: block; color: var(--color-text-muted); font-size: var(--text-xs); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tt-scrim { position: fixed; inset: 0; z-index: 40; background: rgba(0, 0, 0, 0.25); opacity: 0; pointer-events: none; transition: opacity 0.2s; }
.tt-scrim--on { opacity: 1; pointer-events: auto; }
.tt-drawer { position: fixed; top: 0; right: 0; bottom: 0; z-index: 41; width: 460px; max-width: 94vw; display: flex; flex-direction: column; border-left: 1px solid var(--color-border-strong); background: var(--color-surface-raised, var(--color-surface)); transform: translateX(100%); transition: transform 0.25s; }
.tt-drawer--on { transform: none; }
/* On a phone the preview is above the tabs; this button is the way between them (TS-04) */
.tt-fab { position: fixed; inset-inline: 0; inset-block-end: 16px; margin-inline: auto; width: max-content; z-index: 35; display: inline-flex; align-items: center; gap: 8px; min-height: 44px; padding: 0 20px; border: 0; border-radius: var(--shape-control); background: var(--color-primary); color: var(--color-on-primary); font: 600 11px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; box-shadow: var(--shadow-md); cursor: pointer; }
.tt-fab:focus-visible { outline: 2px solid var(--color-brass); outline-offset: 3px; }
.tt-dh { display: flex; align-items: center; gap: 10px; padding: 14px 18px; border-bottom: 1px solid var(--color-border); }
.tt-db { flex: 1; overflow: auto; padding: 16px 18px; }
@media (max-width: 900px) {
  .tt { height: auto; min-height: 0; padding: 12px; }
    .tt-well { flex: none; height: 460px; }
  .tt-body { flex: none; flex-direction: column; }
  .tt-head :deep(.rs-btn) { flex: 1 1 auto; }
  .tt-themes { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tt-q { flex: 1 1 100%; }
  .tt-head { margin: -12px -12px 4px; } /* the bar is as wide as the page, not 12 px wider (TS-03) */
  .tt-sbar { flex-wrap: wrap; }
  .tt-name { flex: 1 1 100%; }
  .tt-sbar .tp-chips button, .tt-dh .tp-chips button, .tt-head :deep(.rs-btn) { min-height: 44px; } /* touch targets (TS-13) */
  .tt-tabs button { min-height: 44px; }
  .tt-tray { scroll-margin-top: 8px; }
  .tt-root { padding-bottom: 72px; }
  .tt-stage { flex: none; order: -1; }
  .tt-tray { flex: none; width: auto; }
  .tt-pane { overflow: visible; }
}
@media (prefers-reduced-motion: reduce) { .tt-tray, .tt-drawer, .tt-scrim { transition: none; } }
</style>
