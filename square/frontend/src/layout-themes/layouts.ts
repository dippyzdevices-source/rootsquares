// The layout themes (rootsquares W9-R5; not in bca-oslo). A theme is tokens plus structure: the tokens are the --t-* values in
// styles/square-layout-themes.css; the structure is this registry: a shell (header, navigation, footer arrangement), a hero, and one variant for
// each section of the home page. Adding a theme means adding it to design/tenant-layouts-v3/layout-themes.json and running
// scripts/build_layout_themes.py; no page code changes.
// paper-brick (the default, bca-oslo's own look) has no layout here: a square on it keeps the original header, home page and footer.
import { squareProfile } from '../services/squareConfig'
import { DARK_BY_DEFAULT, GENERATED_ENGINES, GENERATED_LAYOUTS } from './layouts.generated'

// The shell families: nine single-theme shells and six shared ones (bar, neubar, rail, saas, dock, torn) that the second set of themes configure.
export type ShellKind = 'engine' | 'harvest' | 'still' | 'fjord' | 'pencil' | 'olive' | 'berry' | 'atrium' | 'ledger' | 'marquee' | 'bar' | 'neubar' | 'rail' | 'saas' | 'dock' | 'torn'
export type HeroKind = 'asym' | 'quiet' | 'swiss' | 'zine' | 'arch' | 'berry' | 'full' | 'front' | 'giant' | 'leaf' | 'softgrid' | 'emboss' | 'pearl' | 'product' | 'daylight' | 'torn' | 'cafe' | 'organic' | 'japandi' | 'engine'
export type EventsVariant = 'list' | 'timeline' | 'cards' | 'notes' | 'media' | 'strip' | 'table' | 'giant' | 'tiles' | 'neu' | 'datarows' | 'agenda' | 'round' | 'blobs' | 'bento'
export type GalleryVariant = 'masonry' | 'film' | 'mosaic' | 'polaroid' | 'uniform' | 'feature' | 'framed' | 'blob' | 'grid'
export type NewsVariant = 'lead' | 'index' | 'cols' | 'cards'
export type HeritageVariant = 'years' | 'essay' | 'stack'
export type MembershipVariant = 'cards' | 'rows' | 'band'
export type ContactVariant = 'split' | 'letter' | 'card'
export type SectionHeadKind = 'rule' | 'center' | 'num' | 'hand' | 'caps' | 'pill' | 'soft'
export type FooterKind = 'cols' | 'line' | 'big' | 'band'
export type SectionKey = 'events' | 'heritage' | 'gallery' | 'news' | 'membership'

export interface LayoutDef {
  name: string
  /** The theme's own name for its shell (used in class names). */
  shell: string
  /** The shell family when several themes share one (bar, neubar, rail, saas, dock, torn). */
  sf?: ShellKind
  hero: HeroKind
  ev: EventsVariant
  gal: GalleryVariant
  news: NewsVariant
  her: HeritageVariant
  mem: MembershipVariant
  con: ContactVariant
  sh: SectionHeadKind
  ft: FooterKind
  order: SectionKey[]
  /** Width of the page content, in pixels. */
  mw: number
  /** Side padding of the page content on a wide site, in pixels. */
  px: number
  /** Corner radius of cards and pictures, in pixels. */
  r: number
  /** Corner radius of buttons when it differs from the cards'. */
  br?: number
  /** Buttons and some headings in capitals. */
  caps?: 1
  /** Display font weight. */
  dw: number
  /** Bar shell: header alignment (left or centre), the button kind in it, and pill navigation. */
  hb?: 'left' | 'center'
  hbk?: string
  nav?: 'pill'
  /** Navigation in capitals. */
  nc?: 'uppercase'
  /** Soft pressed (neumorphic) surfaces and their depth in pixels. */
  neu?: 1
  nd?: number
  /** The emphasised part of the headline is upright and coloured (emc 'pa' = the panel accent). */
  emn?: 1
  emc?: 'pa'
  /** Corner radius of pictures when it differs from the cards' (any CSS radius). */
  ir?: string
  /** Radius of the footer band. */
  fr?: string
  /** Every second home section sits on a tinted band; altR rounds it. */
  alt?: 1
  altR?: number
  /** Engine themes (W9-R10): the shell, corner scale and layout kits the layout was made from; `kit` is the kit of the home page. */
  engine?: EngineDef
  kit?: Kit
}

/** The shell family of a layout. */
export const shellOf = (l: LayoutDef): ShellKind => (l.engine ? 'engine' : (l.sf ?? (l.shell as ShellKind)))

/** The width under which every theme falls back to the compact header, measured on the site container, not the window. */
export const COMPACT_BELOW = 860

export const LAYOUTS = GENERATED_LAYOUTS as unknown as Record<string, LayoutDef>

/** An engine theme (W9-R10): one of six navigation shells, a layout kit for each of six slots, a corner scale. */
export type EngineShell = 'bar' | 'side' | 'right' | 'mast' | 'tabs' | 'dock'
export type Kit = 'K1' | 'K2' | 'K3' | 'K4' | 'K5'
export interface EngineDef {
  name: string
  shell: EngineShell
  /** Kits of the slots: [0] rows of events and news, then the sections of the home page and lists. */
  mix: Kit[]
  rs: number
  rp: number
  mode: 'light' | 'dark'
  r: number
  dw: number
}
export const ENGINES = GENERATED_ENGINES as unknown as Record<string, EngineDef>
export const engineFor = (themeId: string): EngineDef | null => ENGINES[themeId] ?? null
/** True when the theme opens dark until the visitor chooses (the square's own default stays light). */
export const opensDark = (themeId: string): boolean => DARK_BY_DEFAULT.includes(themeId)

export function layoutFor(themeId: string): LayoutDef | null {
  return LAYOUTS[themeId] ?? null
}

// The layout kits of the engine themes (design/tenant-themes-v7): K1 cards, K2 rows, K3 ledger, K4 timeline, K5 bento. Slots of a theme's mix: [0] the
// home page, [1] the events page, [2] the committee page, [3] the gallery page, [4] the membership page, [5] the news page.
const EVENTS_OF: Record<Kit, EventsVariant> = { K1: 'cards', K2: 'list', K3: 'table', K4: 'agenda', K5: 'bento' }
const GALLERY_OF: Record<Kit, GalleryVariant> = { K1: 'framed', K2: 'masonry', K3: 'grid', K4: 'film', K5: 'mosaic' }
const NEWS_OF: Record<Kit, NewsVariant> = { K1: 'cards', K2: 'index', K3: 'cols', K4: 'index', K5: 'lead' }
const MEMBERSHIP_OF: Record<Kit, MembershipVariant> = { K1: 'cards', K2: 'rows', K3: 'rows', K4: 'cards', K5: 'band' }

/** The layout of an engine theme, in the shape the shells, headings and lists already read. */
export function engineLayout(e: EngineDef): LayoutDef {
  return {
    name: e.name, shell: 'engine', hero: 'engine', ev: EVENTS_OF[e.mix[1]!], gal: GALLERY_OF[e.mix[3]!], news: NEWS_OF[e.mix[5]!], her: 'years', mem: MEMBERSHIP_OF[e.mix[4]!],
    con: 'card', sh: 'rule', ft: 'band', order: ['events', 'heritage', 'gallery', 'news', 'membership'], mw: 1160, px: 40, r: e.r, br: e.rp > 100 ? 999 : e.rp, dw: e.dw, engine: e, kit: e.mix[0]!,
  }
}

/** The layout of this square, or null (the square keeps the original look). */
export const activeLayout: LayoutDef | null = layoutFor(squareProfile.themeId) ?? (engineFor(squareProfile.themeId) ? engineLayout(engineFor(squareProfile.themeId)!) : null)

/** Under this width of the site container the compact header replaces the theme's: 1120 px for the sidebars and the bar of the engine themes, else 860. */
export const compactBelow = (l: LayoutDef | null): number => (l?.engine && ['side', 'right', 'bar'].includes(l.engine.shell) ? 1120 : COMPACT_BELOW)
