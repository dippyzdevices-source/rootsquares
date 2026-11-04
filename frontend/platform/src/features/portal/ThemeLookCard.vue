<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import { errorText } from '@/features/platform/errorText'
import { platform, type ThemeLook } from '@/services/platform'
import { ALL_THEMES } from '@rootsquares/ui/themes'
import { THEME_COLORS } from '@/themes/colors'
import { STARTING_LOOKS, type StartingLook } from '@/themes/startingLooks'
import { SPINNER_ART } from '@/themes/spinnerSets'
import FontPicker from './FontPicker.vue'
import { ACCENT_CHOICES } from '@/themes/googleFonts'
import { ALL_SCHEMES, FONT_PAIRS, FEEL_PARTS, SHAPE_PARTS, isHex, presetColours, type FeelLookChoice, type Seeds, type ShapeLookChoice } from '@/themes/lookPresets'
import SpinnerPicker from './SpinnerPicker.vue'
import type { LookState } from './lookState'
import { useSquare } from './squareContext'

// "Your own colours and fonts" on the Theme page (W18-R19, docs/plans/themes-dynamic-plan.md step 5): a colour scheme (a ready-made one, or three colours of the owner's own)
// and a font pair, on top of the square's theme. Every change is shown at once in the preview ('preview' event, answered by the square app's bridge); Save look stores it
// (PUT /squares/:id/theme with `overrides`), Back to the theme's own look clears it. Square package and above (W18-R14); below that the card is shown, greyed, with one line.
// The square app keeps the text readable whatever is picked, so there is no contrast checker here.
// The "Aa" of a font card needs the face on the platform page: the ones the platform already has installed are loaded when the Fonts tab is first opened (the others show in the fallback).
const FACE_CSS: Record<string, () => Promise<unknown>> = {
  Marcellus: () => import('@fontsource/marcellus/latin-400.css'), 'DM Serif Display': () => import('@fontsource/dm-serif-display/latin-400.css'),
  'Playfair Display': () => import('@fontsource/playfair-display/latin-400.css'), Sora: () => import('@fontsource/sora/latin-400.css'),
  'Instrument Serif': () => import('@fontsource/instrument-serif/latin-400.css'), 'Libre Baskerville': () => import('@fontsource/libre-baskerville/latin-400.css'),
  'Young Serif': () => import('@fontsource/young-serif/latin-400.css'), 'Schibsted Grotesk': () => import('@fontsource/schibsted-grotesk/latin-400.css'),
  'Bricolage Grotesque': () => import('@fontsource/bricolage-grotesque/latin-600.css'), 'Cormorant Garamond': () => import('@fontsource/cormorant-garamond/latin-500.css'),
}
let facesLoaded = false
// Every pair's two faces (one regular weight each) from Google Fonts, for the samples on the font cards; the ones installed above show at once, the rest as soon as this loads (until then the fallback).
function loadSampleFaces() {
  const names = [...new Set(FONT_PAIRS.flatMap((f) => [f.display, f.body]))]
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = `https://fonts.googleapis.com/css2?${names.map((n) => `family=${n.replace(/ /g, '+')}`).join('&')}&display=swap`
  document.head.appendChild(link)
}
const props = defineProps<{ themeId?: string; section: 'theme' | 'looks' | 'colours' | 'fonts' | 'spinners' | 'shapes' | 'feel' }>() // the theme picked on the page (not yet applied), else the square's own; the tab shown
watch(() => props.section, (s) => { if (s === 'fonts' && !facesLoaded) { facesLoaded = true; for (const f of Object.values(FACE_CSS)) void f().catch(() => undefined); loadSampleFaces() } }, { immediate: true })
const emit = defineEmits<{ preview: [look: ThemeLook | null]; state: [s: LookState]; mode: [m: 'light' | 'dark'] }>()
const { t } = useI18n()
const { sq, set } = useSquare()

// A theme that opens dark (4 of 56, W18-R21): the three colours describe its dark look and the light look is made from them; otherwise the other way round.
const tid = computed(() => props.themeId ?? sq.value?.theme_id ?? '')
const darkFirst = computed(() => ALL_THEMES.find((x) => x.id === tid.value)?.mode === 'dark')
const seedMode = computed<'light' | 'dark'>(() => (darkFirst.value ? 'dark' : 'light'))
const suffix = computed(() => (darkFirst.value ? 'Dark' : ''))
// What the structure brings by itself (step 4): its own colours (in the mode the three colours describe) and its own font pair, shown on the "as the theme is designed" choices.
const own = computed(() => ALL_THEMES.find((x) => x.id === tid.value))
const ownSwatch = computed(() => { const c = THEME_COLORS[tid.value]?.[seedMode.value]; return c ? [c.bg, c.ink, c.accent] : [] })
const allowed = computed(() => sq.value?.launch_package === 'square' || sq.value?.launch_package === 'grove')
const colors = ref<Seeds | null>(null)
const colorsDark = ref<Seeds | null>(null) // the dark look's own three colours; none = made from the light ones (W18-R52)
const fonts = ref<string | null>(null)
const type = ref<ThemeLook['type']>(null) // the owner's own heading, body and accent fonts on top of the pair (W25-R63)
const spinners = ref<string[]>([]) // the spinners the square keeps; none = the nine of the festival set (W18-R28)
const shape = ref<ShapeLookChoice>({}) // button, card, photo frame and edge shapes; a part not chosen is the theme as designed (W18 shapes step 7)
const feel = ref<FeelLookChoice>({}) // default mode, switch, density and motion; a part not chosen is the theme as designed (W18-R44)
const busy = ref(false)
const error = ref('')
const done = ref('')

const saved = computed<ThemeLook>(() => ({ colors: sq.value?.theme_overrides?.colors ?? null, colors_dark: sq.value?.theme_overrides?.colors_dark ?? null, fonts: sq.value?.theme_overrides?.fonts ?? null, spinners: sq.value?.theme_overrides?.spinners?.length ? [...sq.value.theme_overrides.spinners] : null, shape: sq.value?.theme_overrides?.shape ? { ...sq.value.theme_overrides.shape } : null, feel: sq.value?.theme_overrides?.feel ? { ...sq.value.theme_overrides.feel } : null, type: sq.value?.theme_overrides?.type ? JSON.parse(JSON.stringify(sq.value.theme_overrides.type)) : null }))
const draft = computed<ThemeLook>(() => ({ colors: colors.value, colors_dark: colorsDark.value, fonts: fonts.value, spinners: spinners.value.length ? [...spinners.value] : null, shape: Object.keys(shape.value).length ? { ...shape.value } : null, feel: Object.keys(feel.value).length ? { ...feel.value } : null, type: type.value && Object.keys(type.value).length ? JSON.parse(JSON.stringify(type.value)) : null }))
const same = (a: ThemeLook, b: ThemeLook) => JSON.stringify([a.colors, a.colors_dark ?? null, a.fonts, a.spinners ?? null, a.shape ?? null, a.feel ?? null, a.type ?? null]) === JSON.stringify([b.colors, b.colors_dark ?? null, b.fonts, b.spinners ?? null, b.shape ?? null, b.feel ?? null, b.type ?? null])
const dirty = computed(() => !same(draft.value, saved.value))
const hasAny = computed(() => !!(draft.value.colors || draft.value.colors_dark || draft.value.fonts || draft.value.spinners || draft.value.shape || draft.value.feel || draft.value.type))
const hasSaved = computed(() => !!(saved.value.colors || saved.value.colors_dark || saved.value.fonts || saved.value.spinners || saved.value.shape || saved.value.feel || saved.value.type))

// start from what is saved whenever the square (or its saved look) changes under us
watch(() => sq.value?.id, () => { colors.value = saved.value.colors ? { ...saved.value.colors } : null; colorsDark.value = saved.value.colors_dark ? { ...saved.value.colors_dark } : null; fonts.value = saved.value.fonts; spinners.value = saved.value.spinners ? [...saved.value.spinners] : []; shape.value = saved.value.shape ? { ...saved.value.shape } : {}; feel.value = saved.value.feel ? { ...saved.value.feel } : {}; type.value = saved.value.type ? JSON.parse(JSON.stringify(saved.value.type)) : null }, { immediate: true })
// the preview frame shows colours, fonts, shapes and feel; the kept spinners are only saved (a loading screen is rarely on screen in the preview)
watch(draft, (v) => emit('preview', v.colors || v.colors_dark || v.fonts || v.shape || v.feel || v.type ? { colors: v.colors ? { ...v.colors } : null, colors_dark: v.colors_dark ? { ...v.colors_dark } : null, fonts: v.fonts, shape: v.shape ? { ...v.shape } : null, feel: v.feel ? { ...v.feel } : null, type: v.type ? JSON.parse(JSON.stringify(v.type)) : null } : null), { immediate: true, deep: true })

const presets = computed(() => ALL_SCHEMES.flatMap((s) => { const c = presetColours(s.id, seedMode.value); return c ? [{ id: s.id, name: s.name, group: s.group, c }] : [] }))
const same3 = (a: Seeds | null, b: Seeds) => !!a && a.bg === b.bg && a.ink === b.ink && a.acc === b.acc
const FIELDS = ['bg', 'ink', 'acc'] as const

// "My own colours" (W18-R32): opens the three pickers below the choices whatever is set now (before, a click did nothing while a ready-made scheme was on); it stays open until a scheme or the theme's own is chosen.
const customOpen = ref(false)
const isCustom = computed(() => !!colors.value && (customOpen.value || !presets.value.some((p) => same3(colors.value, p.c))))
// Editing the light colours shows the preview in Light, editing the dark colours shows it in Dark (W25-R60); on a theme that opens dark the three colours are its dark look.
const showSide = (m: 'light' | 'dark') => emit('mode', darkFirst.value ? 'dark' : m)
function useScheme(c: Seeds) { showSide('light'); colors.value = { ...c }; customOpen.value = false; done.value = '' }
function ownColours() { showSide('light'); colors.value = colors.value ?? presetColours(tid.value, seedMode.value) ?? presetColours('paper-brick')!; customOpen.value = true; done.value = '' }
function asDesigned() { colors.value = null; colorsDark.value = null; customOpen.value = false; darkOpen.value = false; done.value = '' }

// Dark mode colours (W18-R52): by default the dark look is made from the three colours above; the owner can give it three of its own, or the dark side of a ready-made scheme.
// Not for a structure that opens dark: there the three colours above already are its dark look.
const darkPresets = computed(() => ALL_SCHEMES.flatMap((s) => { const c = presetColours(s.id, 'dark'); return c ? [{ id: s.id, name: s.name, group: s.group, c }] : [] }))
const darkOpen = ref(false)
const darkOwn = computed(() => !!colorsDark.value && (darkOpen.value || !darkPresets.value.some((p) => same3(colorsDark.value, p.c))))
function darkAuto() { emit('mode', 'dark'); colorsDark.value = null; darkOpen.value = false; done.value = '' }
function useDark(c: Seeds) { emit('mode', 'dark'); colorsDark.value = { ...c }; darkOpen.value = false; done.value = '' }
function ownDark() { emit('mode', 'dark'); colorsDark.value = colorsDark.value ?? presetColours(tid.value, 'dark') ?? presetColours('paper-brick', 'dark')!; darkOpen.value = true; done.value = '' }
function setDarkField(k: (typeof FIELDS)[number], v: string) { if (colorsDark.value && isHex(v)) { emit('mode', 'dark'); colorsDark.value = { ...colorsDark.value, [k]: six(v) }; darkOpen.value = true; hexBad.value = { ...hexBad.value, ['d' + k]: false } }; done.value = '' }
const six = (v: string) => { const h = v.trim().replace(/^#/, '').toLowerCase(); return '#' + (h.length === 3 ? h.split('').map((c) => c + c).join('') : h) }
// The hex boxes (TS-10): a full code applies as it is typed, a part of one waits; when the box is left with something that is not a colour it says so and the last good colour stays.
const hexBad = ref<Record<string, boolean>>({})
const hexOk = (v: string) => /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.test(v.trim())
const hexFix = (v: string) => (v.trim().startsWith('#') ? v.trim() : `#${v.trim()}`)
function typeHex(scope: 'l' | 'd', k: (typeof FIELDS)[number], e: Event) {
  const v = (e.target as HTMLInputElement).value
  if (/^#[0-9a-f]{6}$/i.test(v.trim())) { if (scope === 'l') setField(k, v); else setDarkField(k, v) }
}
function leaveHex(scope: 'l' | 'd', k: (typeof FIELDS)[number], e: Event) {
  const el = e.target as HTMLInputElement
  if (!el.isConnected) return // a box that was taken away (Discard, a scheme was chosen) must not write its old text back
  if (!hexOk(el.value)) { hexBad.value = { ...hexBad.value, [scope + k]: true }; return }
  if (scope === 'l') setField(k, hexFix(el.value)); else setDarkField(k, hexFix(el.value))
  el.value = (scope === 'l' ? colors.value?.[k] : colorsDark.value?.[k]) ?? el.value
}
function setField(k: (typeof FIELDS)[number], v: string) { if (colors.value && isHex(v)) { showSide('light'); colors.value = { ...colors.value, [k]: six(v) }; customOpen.value = true; hexBad.value = { ...hexBad.value, ['l' + k]: false } }; done.value = '' }
function pickFont(id: string | null) { fonts.value = id; done.value = '' }
// The owner's own fonts (W25-R63): a heading font, a body font and the accent lines, each a part that is not chosen keeps the pair's (or the theme's) own.
function setType(part: 'display' | 'body' | 'accent', v: unknown) {
  const next = { ...(type.value ?? {}) } as NonNullable<ThemeLook['type']>
  if (v) (next as Record<string, unknown>)[part] = v
  else delete (next as Record<string, unknown>)[part]
  type.value = Object.keys(next).length ? next : null
  done.value = ''
}
const pickAccent = (id: string) => setType('accent', type.value?.accent === id ? null : id)
const spinnerOrder = new Map(SPINNER_ART.map((a, i) => [a.id, i]))
function keepSpinners(ids: string[]) { spinners.value = [...ids].sort((a, b) => (spinnerOrder.get(a) ?? 99) - (spinnerOrder.get(b) ?? 99)); done.value = '' } // always in the catalogue's order (TS-27)
// a click on the chosen option clears it (the theme as designed); a click on another one chooses it
function pickFeel(part: string, id: string) { const next = { ...feel.value }; if (next[part as keyof FeelLookChoice] === id) delete next[part as keyof FeelLookChoice]; else next[part as keyof FeelLookChoice] = id; feel.value = next; done.value = '' }
function pickShape(part: string, id: string) { const next = { ...shape.value }; if (next[part as keyof ShapeLookChoice] === id) delete next[part as keyof ShapeLookChoice]; else next[part as keyof ShapeLookChoice] = id; shape.value = next; done.value = '' }

// Starting looks (W18-R46): one click fills colours, fonts, shape and feel in the draft (the spinners stay); the other tabs then show the parts and the owner changes any of them.
// A look also carries the dark side of its colour scheme (W25-R59), so choosing it changes Dark as well; a theme that opens dark has only the one set.
const starts = computed(() => STARTING_LOOKS.flatMap((s) => { const c = presetColours(s.scheme, seedMode.value); return c ? [{ ...s, c, d: darkFirst.value ? null : presetColours(s.scheme, 'dark') }] : [] }))
const fontOf = (id: string) => FONT_PAIRS.find((f) => f.id === id)
// The light and dark swatches of a starting look (W25-R59). A look gives three colours for the theme's opening mode; the other mode is made from them the way the site does it
// (square/frontend/src/themes/deriveTokens.ts, the starting colours before its readability pass) when the colour scheme has no dark side of its own.
const hx = (v: string) => { const h = v.replace('#', ''); const f = h.length === 3 ? h.split('').map((c) => c + c).join('') : h; return [0, 2, 4].map((i) => parseInt(f.slice(i, i + 2), 16)) }
const mixHex = (a: string, b: string, t: number) => '#' + hx(a).map((x, i) => Math.round(x + (hx(b)[i]! - x) * t).toString(16).padStart(2, '0')).join('')
function otherSide(c: Seeds, from: 'light' | 'dark'): Seeds {
  return from === 'light'
    ? { bg: mixHex(c.ink, '#000000', 0.55), ink: mixHex(c.bg, '#ffffff', 0.3), acc: mixHex(c.acc, '#ffffff', 0.25) }
    : { bg: mixHex(c.ink, '#ffffff', 0.9), ink: mixHex(c.bg, '#000000', 0.4), acc: mixHex(c.acc, '#000000', 0.25) }
}
const sides = (s: { c: Seeds; d: Seeds | null }): { light: Seeds; dark: Seeds } => (seedMode.value === 'dark' ? { light: otherSide(s.c, 'dark'), dark: s.c } : { light: s.c, dark: s.d ?? otherSide(s.c, 'light') })
const startOn = (s: StartingLook & { c: Seeds; d: Seeds | null }) => same3(colors.value, s.c) && (darkFirst.value || (s.d ? same3(colorsDark.value, s.d) : !colorsDark.value)) && fonts.value === s.fonts && !type.value && JSON.stringify(shape.value) === JSON.stringify(s.shape) && JSON.stringify(feel.value) === JSON.stringify(s.feel)
function useStart(s: StartingLook & { c: Seeds; d: Seeds | null }) { colors.value = { ...s.c }; colorsDark.value = s.d ? { ...s.d } : null; darkOpen.value = false; customOpen.value = false; fonts.value = s.fonts; type.value = null; shape.value = { ...s.shape }; feel.value = { ...s.feel }; done.value = '' }

async function save(look: ThemeLook | null) {
  if (!sq.value) return
  busy.value = true
  error.value = ''
  done.value = ''
  try {
    set(await platform.setSquareLook(sq.value.id, look))
    colors.value = saved.value.colors ? { ...saved.value.colors } : null
    colorsDark.value = saved.value.colors_dark ? { ...saved.value.colors_dark } : null
    fonts.value = saved.value.fonts
    spinners.value = saved.value.spinners ? [...saved.value.spinners] : []
    shape.value = saved.value.shape ? { ...saved.value.shape } : {}
    feel.value = saved.value.feel ? { ...saved.value.feel } : {}
    type.value = saved.value.type ? JSON.parse(JSON.stringify(saved.value.type)) : null
    done.value = look ? t('portal.theme.look.saved') : t('portal.theme.look.cleared')
  } catch (e) { error.value = errorText(t, e) } finally { busy.value = false }
}
const saveLook = () => save(hasAny.value ? draft.value : null)
// Back to the theme's own look (W18-R30): the draft is emptied and the page's save bar then stores it; nothing is saved here.
// Discard (TS-05): everything in the editor goes back to what is saved
function discard() {
  (document.activeElement as HTMLElement | null)?.blur?.() // a hex box being edited is left first, then everything goes back
  const s = saved.value
  colors.value = s.colors ? { ...s.colors } : null; colorsDark.value = s.colors_dark ? { ...s.colors_dark } : null; fonts.value = s.fonts; spinners.value = s.spinners ? [...s.spinners] : []
  shape.value = s.shape ? { ...s.shape } : {}; feel.value = s.feel ? { ...s.feel } : {}; type.value = s.type ? JSON.parse(JSON.stringify(s.type)) : null; customOpen.value = false; darkOpen.value = false; hexBad.value = {}; done.value = ''
}
function reset() { colors.value = null; colorsDark.value = null; fonts.value = null; type.value = null; spinners.value = []; shape.value = {}; feel.value = {}; done.value = '' }
const colourName = computed(() => (!colors.value ? t('portal.theme.look.designed') : (presets.value.find((p) => same3(colors.value, p.c))?.name ?? t('portal.theme.look.own'))))
const fontName = computed(() => FONT_PAIRS.find((f) => f.id === fonts.value)?.label ?? t('portal.theme.look.fontsDesigned'))
const feelName = computed(() => { const n = FEEL_PARTS.filter((p) => feel.value[p.id]).length; return n ? t('portal.theme.look.feelChosen', { n }) : t('portal.theme.look.designed') })
const shapeName = computed(() => { const n = SHAPE_PARTS.filter((p) => shape.value[p.id]).length; return n ? t('portal.theme.look.shapesChosen', { n }) : t('portal.theme.look.designed') })
watch([dirty, hasAny, hasSaved, busy, colourName, fontName, shapeName, feelName, spinners], () => emit('state', { dirty: dirty.value, hasAny: hasAny.value, hasSaved: hasSaved.value, busy: busy.value, allowed: allowed.value, colourName: colourName.value, fontName: fontName.value, shapeName: shapeName.value, feelName: feelName.value, kept: spinners.value.length }), { immediate: true, deep: true })
// The shared draft (W18-R47, ThemeDraftPanel.vue) saves what is in the editor and can load it back.
function current(): ThemeLook { return { ...draft.value, spinners: draft.value.spinners ? [...draft.value.spinners] : null } }
function load(look: Partial<ThemeLook>) { colors.value = look.colors ? { ...look.colors } : null; colorsDark.value = look.colors_dark ? { ...look.colors_dark } : null; darkOpen.value = false; fonts.value = look.fonts ?? null; spinners.value = look.spinners ? [...look.spinners] : []; shape.value = look.shape ? { ...look.shape } : {}; feel.value = look.feel ? { ...look.feel } : {}; type.value = look.type ? JSON.parse(JSON.stringify(look.type)) : null; customOpen.value = false; done.value = '' }
defineExpose({ saveLook, reset, discard, current, load })
</script>

<template>
  <div v-if="sq" class="tl" :class="{ 'tl--locked': !allowed }">
    <!-- below the Square package: say what it gives and offer the way up (Billing) and a way to ask (W26-R13) -->
    <template v-if="!allowed">
      <AppAlert tone="info">{{ t('portal.theme.look.locked') }}</AppAlert>
      <p class="tl-pitch">{{ t('lockedLook.pitch') }}</p>
      <div class="tl-sell" data-testid="theme-look-locked">
        <AppButton icon="card" :to="`/squares/${sq.id}/billing`">{{ t('siteDomain.upgrade', { package: t('marketing.pricing.launch.square.name') }) }}</AppButton>
        <AppButton icon="send" variant="secondary" to="/contact">{{ t('siteDomain.talkButton') }}</AppButton>
      </div>
    </template>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
    <AppAlert v-if="done" tone="success">{{ done }}</AppAlert>

    <fieldset v-show="section === 'looks'" class="tl-set" :disabled="!allowed || busy">
      <legend class="tl-leg">{{ t('portal.theme.look.starts') }}</legend>
      <p v-if="hasAny" class="tl-back"><AppButton icon="chevron-left" variant="ghost" size="sm" @click="reset">{{ t('portal.theme.look.back') }}</AppButton></p>
      <p class="bs-mute tl-note">{{ t('portal.theme.look.startsLede') }}</p>
      <p class="tl-cap"><span class="tl-sw" aria-hidden="true"><b /><b /><b /></span>{{ t('portal.theme.look.swCaption') }}</p>
      <div class="tl-starts" role="group" :aria-label="t('portal.theme.look.starts')">
        <button v-for="s in starts" :key="s.id" type="button" class="tl-start" :aria-pressed="startOn(s)" @click="useStart(s)">
          <span class="tl-pair">
            <span v-for="m in (['light', 'dark'] as const)" :key="m" class="tl-side"><small>{{ t(`portal.theme.look.sw_${m}`) }}</small><i class="tl-sw"><b :style="{ background: sides(s)[m].bg }" /><b :style="{ background: sides(s)[m].ink }" /><b :style="{ background: sides(s)[m].acc }" /></i></span>
          </span>
          <span class="tl-aa" :style="{ fontFamily: `'${fontOf(s.fonts)?.display}', serif` }">Aa</span>
          <b>{{ s.name }}</b><small>{{ s.hint }}</small>
        </button>
      </div>
      <p class="bs-mute tl-note">{{ t('portal.theme.look.startsNote') }}</p>
      <p v-if="!darkFirst" class="bs-mute tl-note">{{ t('portal.theme.look.startsDark') }}</p>
    </fieldset>

    <fieldset v-show="section === 'colours'" class="tl-set" :disabled="!allowed || busy">
      <legend class="tl-leg">{{ t('portal.theme.look.colours') }}</legend>
      <p v-if="colors" class="tl-back"><AppButton icon="chevron-left" variant="ghost" size="sm" @click="asDesigned">{{ t('portal.theme.look.backColours') }}</AppButton></p>
      <p class="bs-mute tl-note">{{ t('portal.theme.look.coloursLede') }}</p>
      <p class="tl-cap"><span class="tl-sw" aria-hidden="true"><b /><b /><b /></span>{{ t('portal.theme.look.swCaption') }}</p>
      <div class="tp-chips" role="group" :aria-label="t('portal.theme.look.colours')">
        <button type="button" :aria-pressed="!colors" @click="asDesigned"><i v-if="ownSwatch.length" class="tl-sw"><b v-for="c in ownSwatch" :key="c" :style="{ background: c }" /></i>{{ t('portal.theme.look.designed') }}</button>
        <template v-for="(p, i) in presets" :key="p.id">
          <span v-if="i === 0 || p.group !== presets[i - 1]!.group" class="tl-grp">{{ t(`portal.theme.look.grp_${p.group}`) }}</span>
          <button type="button" :aria-pressed="!isCustom && same3(colors, p.c)" @click="useScheme(p.c)">
            <i class="tl-sw"><b :style="{ background: p.c.bg }" /><b :style="{ background: p.c.ink }" /><b :style="{ background: p.c.acc }" /></i>{{ p.name }}
          </button>
        </template>
        <button type="button" :aria-pressed="isCustom" @click="ownColours">{{ t('portal.theme.look.own') }}</button>
      </div>
      <p v-if="colorsDark && !darkFirst" class="bs-mute tl-note" role="status">{{ t('portal.theme.look.darkSet') }}</p>
      <div v-if="isCustom && colors" class="tl-own">
        <h4 class="tl-own-h">{{ t('portal.theme.look.own') }}</h4>
      <div class="tl-rows">
        <label v-for="k in FIELDS" :key="k" class="tl-row">
          <span class="rs-label">{{ t(`portal.theme.look.${k}${suffix}`) }}</span>
          <span class="tl-pk">
            <input type="color" class="tl-color" :value="colors[k]" :aria-label="t(`portal.theme.look.${k}`)" @input="setField(k, ($event.target as HTMLInputElement).value)" />
            <input class="rs-input tl-hex" :value="colors[k]" maxlength="7" :aria-label="t(`portal.theme.look.${k}Hex`)" :aria-invalid="hexBad['l' + k] ? true : undefined" @input="typeHex('l', k, $event)" @blur="leaveHex('l', k, $event)" @change="leaveHex('l', k, $event)" />
          </span>
          <small v-if="hexBad['l' + k]" class="tl-bad" role="alert">{{ t('portal.theme.look.hexBad') }}</small>
        </label>
      </div>
        <p class="bs-mute tl-note">{{ t(darkFirst ? 'portal.theme.look.readableDark' : 'portal.theme.look.readable') }}</p>
      </div>
      <div v-if="colors && !darkFirst" class="tl-own">
        <h4 class="tl-own-h">{{ t('portal.theme.look.darkTitle') }}</h4>
        <p class="bs-mute tl-note">{{ t('portal.theme.look.darkLede') }}</p>
        <p class="tl-cap"><span class="tl-sw" aria-hidden="true"><b /><b /><b /></span>{{ t('portal.theme.look.swCaption') }}</p>
        <div class="tp-chips" role="group" :aria-label="t('portal.theme.look.darkTitle')">
          <button type="button" :aria-pressed="!colorsDark" @click="darkAuto">{{ t('portal.theme.look.darkAuto') }}</button>
          <template v-for="(p, i) in darkPresets" :key="p.id">
            <span v-if="i === 0 || p.group !== darkPresets[i - 1]!.group" class="tl-grp">{{ t(`portal.theme.look.grp_${p.group}`) }}</span>
            <button type="button" :aria-pressed="!darkOwn && same3(colorsDark, p.c)" @click="useDark(p.c)">
              <i class="tl-sw"><b :style="{ background: p.c.bg }" /><b :style="{ background: p.c.ink }" /><b :style="{ background: p.c.acc }" /></i>{{ p.name }}
            </button>
          </template>
          <button type="button" :aria-pressed="darkOwn" @click="ownDark">{{ t('portal.theme.look.ownDark') }}</button>
        </div>
        <div v-if="darkOwn && colorsDark" class="tl-rows">
          <label v-for="k in FIELDS" :key="k" class="tl-row">
            <span class="rs-label">{{ t(`portal.theme.look.${k}Dark`) }}</span>
            <span class="tl-pk">
              <input type="color" class="tl-color" :value="colorsDark[k]" :aria-label="t(`portal.theme.look.${k}`)" @input="setDarkField(k, ($event.target as HTMLInputElement).value)" />
              <input class="rs-input tl-hex" :value="colorsDark[k]" maxlength="7" :aria-label="t(`portal.theme.look.${k}Hex`)" :aria-invalid="hexBad['d' + k] ? true : undefined" @input="typeHex('d', k, $event)" @blur="leaveHex('d', k, $event)" @change="leaveHex('d', k, $event)" />
            </span>
            <small v-if="hexBad['d' + k]" class="tl-bad" role="alert">{{ t('portal.theme.look.hexBad') }}</small>
          </label>
        </div>
      </div>
    </fieldset>

    <fieldset v-show="section === 'fonts'" class="tl-set" :disabled="!allowed || busy">
      <legend class="tl-leg">{{ t('portal.theme.look.fonts') }}</legend>
      <p v-if="fonts" class="tl-back"><AppButton icon="chevron-left" variant="ghost" size="sm" @click="pickFont(null)">{{ t('portal.theme.look.backFonts') }}</AppButton></p>
      <p class="bs-mute tl-note">{{ t('portal.theme.look.adminFixed') }}</p>
      <div class="tl-type">
        <h4 class="tl-own-h">{{ t('portal.theme.look.typeTitle') }}</h4>
        <p v-if="type" class="tl-back"><AppButton icon="chevron-left" variant="ghost" size="sm" @click="type = null; done = ''">{{ t('portal.theme.look.backType') }}</AppButton></p>
        <p class="bs-mute tl-note">{{ t('portal.theme.look.typeLede') }}</p>
        <FontPicker :label="t('portal.theme.look.typeHeading')" :model-value="type?.display" :fallback="t('portal.theme.look.pickerPair')" :disabled="!allowed || busy" @update:model-value="setType('display', $event)" />
        <FontPicker :label="t('portal.theme.look.typeBody')" :model-value="type?.body" :fallback="t('portal.theme.look.pickerPair')" :disabled="!allowed || busy" @update:model-value="setType('body', $event)" />
        <div class="tl-type-acc">
          <span class="rs-label">{{ t('portal.theme.look.typeAccent') }}</span>
          <div class="tp-chips" role="group" :aria-label="t('portal.theme.look.typeAccent')">
            <button type="button" :aria-pressed="!type?.accent" @click="setType('accent', null)">{{ t('portal.theme.look.accentOwn') }}</button>
            <button v-for="a in ACCENT_CHOICES" :key="a.id" type="button" :aria-pressed="type?.accent === a.id" @click="pickAccent(a.id)">{{ a.label }}</button>
          </div>
        </div>
        <p class="bs-mute tl-note">* {{ t('portal.theme.look.typeGoogle') }}</p>
      </div>
      <h4 class="tl-own-h tl-pairs-h">{{ t('portal.theme.look.pairsTitle') }}</h4>
      <div class="tl-fonts" role="group" :aria-label="t('portal.theme.look.fonts')">
        <button type="button" class="tl-font" :aria-pressed="!fonts" @click="pickFont(null)">
          <span class="tl-aa" :style="{ fontFamily: own ? `'${own.display}', serif` : undefined }">{{ t('portal.theme.look.fontHead') }}</span>
          <span class="tl-tx" :style="{ fontFamily: own ? `'${own.body}', sans-serif` : undefined }">{{ t('portal.theme.look.fontText') }}</span>
          <b>{{ t('portal.theme.look.fontsDesigned') }}</b><small v-if="own">{{ own.display }} · {{ own.body }}</small>
        </button>
        <button v-for="f in FONT_PAIRS" :key="f.id" type="button" class="tl-font" :aria-pressed="fonts === f.id" :title="`${f.display} + ${f.body}`" @click="pickFont(f.id)">
          <span class="tl-aa" :style="{ fontFamily: `'${f.display}', serif` }">{{ t('portal.theme.look.fontHead') }}</span>
          <span class="tl-tx" :style="{ fontFamily: `'${f.body}', sans-serif` }">{{ t('portal.theme.look.fontText') }}</span>
          <b>{{ f.label }}</b><small>{{ f.display }} · {{ f.body }}</small>
        </button>
      </div>
    </fieldset>

    <fieldset v-show="section === 'shapes'" class="tl-set" :disabled="!allowed || busy">
      <legend class="tl-leg">{{ t('portal.theme.look.shapes') }}</legend>
      <p v-if="Object.keys(shape).length" class="tl-back"><AppButton icon="chevron-left" variant="ghost" size="sm" @click="shape = {}; done = ''">{{ t('portal.theme.look.backShapes') }}</AppButton></p>
      <p class="bs-mute tl-note">{{ t('portal.theme.look.shapesLede') }}</p>
      <div v-for="part in SHAPE_PARTS" :key="part.id" class="tl-shp">
        <h4 class="tl-own-h">{{ t(`portal.theme.look.shape_${part.id}`) }}</h4>
        <div class="tl-shapes" role="group" :aria-label="t(`portal.theme.look.shape_${part.id}`)">
          <button v-for="o in part.options" :key="o.id" type="button" class="tl-shape" :aria-pressed="shape[part.id] === o.id" @click="pickShape(part.id, o.id)">
            <span class="tl-pic" :class="`tl-pic--${part.id}`" :style="{ borderRadius: o.radius, border: o.edge && o.edge !== 'shadow' ? o.edge : undefined, boxShadow: o.edge === 'shadow' ? '0 6px 12px -4px rgba(0,0,0,.35)' : undefined }" />
            <b>{{ o.label }}</b>
          </button>
        </div>
      </div>
      <p class="bs-mute tl-note">{{ t('portal.theme.look.shapesAdmin') }}</p>
    </fieldset>

    <fieldset v-show="section === 'feel'" class="tl-set" :disabled="!allowed || busy">
      <legend class="tl-leg">{{ t('portal.theme.look.feel') }}</legend>
      <p v-if="Object.keys(feel).length" class="tl-back"><AppButton icon="chevron-left" variant="ghost" size="sm" @click="feel = {}; done = ''">{{ t('portal.theme.look.backFeel') }}</AppButton></p>
      <p class="bs-mute tl-note">{{ t('portal.theme.look.feelLede') }}</p>
      <div v-for="part in FEEL_PARTS" :key="part.id" class="tl-shp">
        <h4 class="tl-own-h">{{ t(`portal.theme.look.feel_${part.id}`) }}</h4>
        <div class="tl-shapes tl-shapes--feel" role="group" :aria-label="t(`portal.theme.look.feel_${part.id}`)">
          <button v-for="o in part.options" :key="o.id" type="button" class="tl-shape tl-feel" :aria-pressed="feel[part.id] === o.id" @click="pickFeel(part.id, o.id)">
            <b>{{ o.label }}</b><small>{{ o.hint }}</small>
          </button>
        </div>
        <!-- A sample of the chosen divider and motion, so the choice can be seen without searching the preview (W25-R56) -->
        <div v-if="part.id === 'divider'" class="tl-demo" :aria-label="t('portal.theme.look.demoDivider')">
          <span class="tl-demo-cap">{{ t('portal.theme.look.demoDivider') }}</span>
          <div v-if="(feel.divider ?? 'glyph') !== 'none'" class="tl-motif"><span /><i v-if="(feel.divider ?? 'glyph') === 'glyph'" aria-hidden="true">❖</i><span /></div>
          <span v-else class="bs-mute tl-demo-none">{{ t('portal.theme.look.demoNothing') }}</span>
        </div>
        <div v-if="part.id === 'motion'" class="tl-demo" :aria-label="t('portal.theme.look.demoMotion')">
          <span class="tl-demo-cap">{{ t('portal.theme.look.demoMotion') }}</span>
          <div class="tl-demo-row">
            <div class="tl-lift" :class="{ 'tl-lift--still': ['calm', 'nolift'].includes(feel.motion ?? 'lively') }" tabindex="0">{{ t('portal.theme.look.demoHover') }}</div>
            <div class="tl-strip" aria-hidden="true"><div class="tl-strip-track" :class="{ 'tl-strip-track--still': ['calm', 'nostrip'].includes(feel.motion ?? 'lively') }"><span v-for="n in 12" :key="n">{{ n % 2 ? 'EVENTS' : 'MEMBERS' }}</span></div></div>
          </div>
        </div>
      </div>
      <p class="bs-mute tl-note">{{ t('portal.theme.look.feelAdmin') }}</p>
    </fieldset>

    <fieldset v-show="section === 'spinners'" class="tl-set" :disabled="!allowed || busy">
      <legend class="tl-leg">{{ t('portal.theme.look.spinners') }}</legend>
      <p v-if="spinners.length" class="tl-back"><AppButton icon="chevron-left" variant="ghost" size="sm" @click="keepSpinners([])">{{ t('portal.theme.look.backSpinners') }}</AppButton></p>
      <p class="bs-mute tl-note">{{ t('portal.theme.look.spinnersLede') }}</p>
      <SpinnerPicker :model-value="spinners" :group-type="sq.group_type ?? null" :disabled="!allowed || busy" @update:model-value="keepSpinners" />
    </fieldset>
  </div>
</template>

<style scoped>
.tl { display: grid; gap: 14px; }
.tl--locked .tl-set { opacity: 0.55; }
.tl-pitch { margin: 0; font-size: var(--text-sm); color: var(--color-text-muted); line-height: 1.45; }
.tl-sell { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; }
.tl-set { border: 0; padding: 0; margin: 0; min-width: 0; display: grid; gap: 10px; }
.tl-leg { padding: 0; margin: 0 0 2px; font: 500 var(--text-lg) var(--font-sans); }
.tl-sw { display: inline-flex; border-radius: 99px; overflow: hidden; border: 1px solid var(--color-border-strong); }
.tl-sw b { width: 12px; height: 16px; display: block; }
.tl-grp { flex: 0 0 100%; margin-top: 6px; font-size: var(--text-xs); letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-text-muted); }
.tl-grp:first-child { margin-top: 0; }
.tl-cap { display: flex; align-items: center; gap: 8px; margin: 0; font-size: var(--text-xs); color: var(--color-text-muted); }
.tl-cap .tl-sw b:nth-child(1) { background: var(--color-surface-sunken); }
.tl-cap .tl-sw b:nth-child(2) { background: var(--color-text); }
.tl-cap .tl-sw b:nth-child(3) { background: var(--color-brass); }
.tl-pair { display: flex; flex-wrap: wrap; gap: 8px 14px; }
.tl-side { display: grid; gap: 2px; justify-items: start; }
.tl-side small { font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-text-muted); }
.tl-own { display: grid; gap: 10px; margin-top: 8px; padding-top: 16px; border-top: 1px solid var(--color-border); }
.tl-own-h { margin: 0; font: 600 0.7rem/1.2 var(--font-sans); letter-spacing: 0.15em; text-transform: uppercase; color: var(--color-brass-text); }
.tl-rows { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
@media (max-width: 640px) { .tl-rows { grid-template-columns: 1fr; } }
.tl-row { display: grid; gap: 5px; min-width: 0; }
.tl-pk { display: flex; gap: 8px; align-items: center; }
.tl-color { width: 44px; height: 36px; padding: 2px; border: 1px solid var(--color-border-strong); border-radius: 6px; background: var(--color-surface); flex: none; }
.tl-hex { font-family: ui-monospace, monospace; min-width: 0; }
.tl-note { margin: 0; font-size: var(--text-xs); }
.tl-bad { color: var(--color-danger); font-size: var(--text-xs); line-height: 1.4; }
.tl-back { margin: 0; }
.tl-type { display: grid; gap: 14px; padding: 14px; border: 1px solid var(--color-border-strong); border-radius: var(--shape-surface); background: var(--color-surface); }
.tl-pairs-h { margin-top: 6px; }
.tl-type-acc { display: grid; gap: 6px; }
.tl-fonts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
@media (max-width: 560px) { .tl-fonts { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.tl-font { display: grid; gap: 2px; justify-items: start; text-align: start; min-width: 0; padding: 12px 14px; border: 1px solid var(--color-border-strong); border-radius: 8px; background: var(--color-surface); color: var(--color-text); font: inherit; cursor: pointer; }
.tl-font:hover { border-color: var(--color-brass); }
.tl-font[aria-pressed='true'] { border-color: var(--color-brass); background: var(--color-brass-subtle); box-shadow: inset 0 0 0 1px var(--color-brass); }
.tl-font:disabled { cursor: default; }
.tl-aa { font-size: 22px; line-height: 1.15; max-width: 100%; overflow-wrap: anywhere; }
.tl-tx { font-size: var(--text-xs); line-height: 1.45; color: var(--color-text-muted); display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.tl-font b { font-weight: 500; font-size: var(--text-sm); margin-top: 6px; }
.tl-font small { color: var(--color-text-muted); font-size: var(--text-xs); max-width: 100%; overflow-wrap: anywhere; }
.tl-font b { max-width: 100%; overflow-wrap: anywhere; }
.tl-starts { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.tl-start { display: grid; gap: 4px; justify-items: start; text-align: start; min-width: 0; padding: 14px; border: 1px solid var(--color-border-strong); border-radius: 12px; background: var(--color-surface); color: var(--color-text); font: inherit; cursor: pointer; }
.tl-start:hover { border-color: var(--color-brass); }
.tl-start[aria-pressed='true'] { border-color: var(--color-brass); background: var(--color-brass-subtle); box-shadow: inset 0 0 0 1px var(--color-brass); }
.tl-start:disabled { cursor: default; }
.tl-start:focus-visible { outline: 2px solid var(--color-focus, var(--color-primary)); outline-offset: 2px; }
.tl-start b { font-weight: 500; font-size: var(--text-sm); }
.tl-start small { color: var(--color-text-muted); font-size: var(--text-xs); }
.tl-shp { display: grid; gap: 8px; }
.tl-shapes { display: grid; grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); gap: 10px; }
.tl-shapes--feel { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
.tl-shape { display: grid; justify-items: center; align-content: start; gap: 6px; min-width: 0; padding: 12px 14px; border: 1px solid var(--color-border-strong); border-radius: 8px; background: var(--color-surface); color: var(--color-text); font: inherit; cursor: pointer; }
.tl-shape:hover { border-color: var(--color-brass); }
.tl-shape[aria-pressed='true'] { border-color: var(--color-brass); background: var(--color-brass-subtle); box-shadow: inset 0 0 0 1px var(--color-brass); }
.tl-shape:disabled { cursor: default; }
.tl-shape:focus-visible { outline: 2px solid var(--color-focus, var(--color-primary)); outline-offset: 2px; }
.tl-shape b { font-weight: 500; font-size: var(--text-xs); }
.tl-feel { justify-items: start; text-align: start; }
.tl-feel small { color: var(--color-text-muted); font-size: var(--text-xs); }
/* the samples of the divider and motion choices (W25-R56) */
.tl-demo { display: grid; gap: 8px; margin-top: 10px; padding: 12px 14px; border: 1px dashed var(--color-border-strong); border-radius: var(--shape-inner); }
.tl-demo-cap { font-size: var(--text-xs); color: var(--color-text-muted); }
.tl-demo-none { font-size: var(--text-xs); }
.tl-motif { display: flex; align-items: center; gap: 12px; color: var(--color-brass-text); }
.tl-motif span { flex: 1; height: 1px; background: var(--color-border-strong); }
.tl-motif i { font-style: normal; font-size: 14px; letter-spacing: 0.4em; }
.tl-demo-row { display: grid; grid-template-columns: minmax(0, 160px) minmax(0, 1fr); gap: 12px; align-items: center; }
.tl-lift { padding: 14px 12px; text-align: center; font-size: var(--text-sm); border: 1px solid var(--color-border); border-radius: var(--shape-inner); background: var(--color-surface); transition: transform 0.25s ease, box-shadow 0.25s ease; cursor: default; }
.tl-lift:not(.tl-lift--still):hover, .tl-lift:not(.tl-lift--still):focus-visible { transform: translateY(-6px); box-shadow: 0 10px 22px -10px rgba(0, 0, 0, 0.35); }
.tl-strip { overflow: hidden; border-radius: 999px; background: var(--color-surface-sunken); padding: 8px 0; }
.tl-strip-track { display: flex; gap: 24px; width: max-content; font-size: var(--text-xs); letter-spacing: 0.14em; color: var(--color-text-muted); animation: tl-scroll 9s linear infinite; }
.tl-strip-track--still { animation-play-state: paused; }
@keyframes tl-scroll { to { transform: translateX(-50%); } }
@media (prefers-reduced-motion: reduce) { .tl-strip-track { animation-play-state: paused; } }
.tl-pic { display: block; width: 52px; height: 32px; background: var(--color-brass-subtle); border: 1.5px solid var(--color-brass); }
.tl-pic--buttons { background: var(--color-brass); height: 30px; }
.tl-pic--photos { height: 40px; }
.tl-font:focus-visible { outline: 2px solid var(--color-focus, var(--color-primary)); outline-offset: 2px; }
</style>
