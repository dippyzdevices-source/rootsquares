/**
 * What it is:   The choices of the "Your own colours and fonts" card on a square's Theme page (rootsquares W18-R19, docs/plans/themes-dynamic-plan.md, step 5).
 * What it does: FONT_PAIRS is the list of 23 font pairs (ids equal to square/frontend/src/themes/fontPairs.ts and backend/app/platform/theme_overrides.py; a test compares them);
 *               COLOUR_SCHEMES lists 16 colour schemes (25 until W25-R62; OWN_SCHEMES adds ten tinted sets), each the three main colours (page, text, accent) of an existing theme under a colour name.
 * How to use:   import { FONT_PAIRS, COLOUR_SCHEMES, presetColours }; the card (features/portal/ThemeLookCard.vue) reads them.
 * Run:          from frontend: npm run test:look
 * Read before:  src/themes/colors.ts (generated palettes).
 * Read after:   features/portal/ThemeLookCard.vue.
 */
import { THEME_COLORS } from './colors'

export interface FontPairChoice { id: string; label: string; display: string; body: string }

export const FONT_PAIRS: FontPairChoice[] = [
  { id: 'classic', label: 'Classic', display: 'Marcellus', body: 'Karla' },
  { id: 'friendly', label: 'Friendly modern', display: 'Bricolage Grotesque', body: 'Figtree' },
  { id: 'editorial', label: 'Editorial serif', display: 'DM Serif Display', body: 'DM Sans' },
  { id: 'elegant', label: 'Elegant', display: 'Cormorant Garamond', body: 'Mulish' },
  { id: 'clean', label: 'Clean and clear', display: 'Sora', body: 'Work Sans' },
  { id: 'dramatic', label: 'High contrast', display: 'Playfair Display', body: 'Karla' },
  { id: 'warm', label: 'Warm serif', display: 'Lora', body: 'Nunito Sans' },
  { id: 'soft', label: 'Soft and rounded', display: 'Quicksand', body: 'Nunito' },
  { id: 'bold', label: 'Bold geometric', display: 'Space Grotesk', body: 'Public Sans' },
  { id: 'playful', label: 'Playful', display: 'Fredoka', body: 'Albert Sans' },
  { id: 'contemporary', label: 'Contemporary', display: 'Instrument Serif', body: 'Instrument Sans' },
  { id: 'scholarly', label: 'Traditional', display: 'Libre Baskerville', body: 'Source Sans 3' },
  { id: 'sturdy', label: 'Warm and sturdy', display: 'Young Serif', body: 'Hanken Grotesk' },
  { id: 'newsroom', label: 'Newsroom', display: 'Schibsted Grotesk', body: 'Newsreader' },
  { id: 'display', label: 'Bold display', display: 'Gloock', body: 'Manrope' },
  { id: 'gallery', label: 'Gallery', display: 'Syne', body: 'Outfit' },
  { id: 'futuristic', label: 'Futuristic friendly', display: 'Unbounded', body: 'Plus Jakarta Sans' },
  { id: 'fashion', label: 'Fashion contrast', display: 'Bodoni Moda', body: 'Jost' },
  { id: 'sansoverserif', label: 'Sans over serif', display: 'Epilogue', body: 'Source Serif 4' },
  { id: 'quirky', label: 'Quirky grotesque', display: 'Familjen Grotesk', body: 'Literata' },
  { id: 'refined', label: 'Refined classic', display: 'Libre Caslon Text', body: 'Albert Sans' },
  { id: 'upbeat', label: 'Playful and bold', display: 'Gabarito', body: 'Nunito Sans' },
  { id: 'literary', label: 'Soft literary', display: 'Newsreader', body: 'Hanken Grotesk' },
]

/**
 * The ready-made colour schemes (W18-R26, docs/plans/themes-composer-plan.md step 3): 16 are the page, text and accent colours of an existing theme (`id`), under a colour name; nine near-duplicates were dropped and ten tinted-page colour sets added in W25-R62 (OWN_SCHEMES below, colours only, no theme).
 * Ordered by hue, warm to cool to neutral. Four come from themes that open dark (citrus-night, neon-cyan, mint-night, mela-noir): on a structure that opens light their
 * light-side colours are used, on mela-noir (the one dark-opening structure offered) their dark-side colours, like every scheme (presetColours takes the mode).
 * A theme whose palette another theme repeats (sand-teal = dune-teal, clay-pastel = clay-press, pearl = pearl-emboss) is listed once.
 */
export const COLOUR_SCHEMES: { id: string; name: string }[] = [
  { id: 'paper-brick', name: 'Brick and saffron' },
  { id: 'ledger-gazette', name: 'Oxblood' },
  { id: 'ruby-pop', name: 'Ruby' },
  { id: 'citrus-night', name: 'Amber night' },
  { id: 'berry-courtyard', name: 'Berry' },
  { id: 'fuchsia-pop', name: 'Fuchsia' },
  { id: 'orchid-dusk', name: 'Orchid' },
  { id: 'daylight', name: 'Indigo and cream' },
  { id: 'fjord-modern', name: 'Electric blue' },
  { id: 'denim-linen', name: 'Denim' },
  { id: 'atrium', name: 'Deep teal' },
  { id: 'sand-teal', name: 'Sand and teal' },
  { id: 'stillwater', name: 'Sage' },
  { id: 'olive-linen', name: 'Olive' },
  { id: 'cacao-mint', name: 'Cocoa' },
  { id: 'mela-noir', name: 'Noir' },
]

/**
 * Ten colour sets of their own (W25-R62): a tinted page (sand, sage, blush, blue, lavender, seafoam, green, navy, wine, grey) with its own dark side (a coloured dark page, dark enough for 7:1 white text, W25-R62), so choosing one changes the whole feel and not
 * only the accent. `l` and `d` are page, text and accent for the light and the dark look. Not themes: a square keeps its theme and gets these colours on top (the checks of
 * square/frontend/src/themes/colourSchemes.spec.ts read this block).
 */
export const OWN_SCHEMES: { id: string; name: string; l: [string, string, string]; d: [string, string, string] }[] = [
  { id: 'sandstone', name: 'Sandstone', l: ['#eadfc8', '#3a2e1f', '#b5651d'], d: ['#3b2a10', '#f1e6d2', '#e0a04a'] },
  { id: 'sage-mist', name: 'Sage mist', l: ['#dde6da', '#1f2d24', '#2f6b4f'], d: ['#24382a', '#e4efe6', '#6fd1a0'] },
  { id: 'blush', name: 'Blush', l: ['#f6ddda', '#3b1f26', '#b03a5b'], d: ['#5a1f3a', '#f8e6ea', '#f07fa0'] },
  { id: 'dusk-blue', name: 'Dusk blue', l: ['#d6dfee', '#1b2438', '#3558b8'], d: ['#243b6b', '#e6ecfa', '#7fa3ff'] },
  { id: 'lavender', name: 'Lavender haze', l: ['#e4ddf0', '#2a2140', '#6b47c2'], d: ['#301a5e', '#eee8fa', '#b49cff'] },
  { id: 'seafoam', name: 'Seafoam', l: ['#cfe9e4', '#12332f', '#0f7a6e'], d: ['#0b3d3a', '#ddf3ef', '#4fd1c0'] },
  { id: 'forest-gold', name: 'Forest and gold', l: ['#e3e8d3', '#22301a', '#4f7a1e'], d: ['#1d4012', '#f0ebd8', '#e0b04a'] },
  { id: 'navy-gold', name: 'Navy and gold', l: ['#e9edf5', '#14233f', '#c07a12'], d: ['#0a1c4a', '#eef1f8', '#f2a33a'] },
  { id: 'wine-gold', name: 'Wine and gold', l: ['#f3e3e0', '#4a1626', '#9a5b0c'], d: ['#3e0f1e', '#f7e9e4', '#f0b25a'] },
  { id: 'graphite', name: 'Graphite', l: ['#e6e7e8', '#26292e', '#2e6f7a'], d: ['#2a2e35', '#f1f1ee', '#5bc0be'] },
]

/** Every scheme the Colours tab offers, in order: the theme-based ones, then the tinted sets (`group` for the heading). */
export const ALL_SCHEMES: { id: string; name: string; group: 'classic' | 'tinted' }[] = [
  ...COLOUR_SCHEMES.map((x) => ({ ...x, group: 'classic' as const })),
  ...OWN_SCHEMES.map((x) => ({ id: x.id, name: x.name, group: 'tinted' as const })),
]

/**
 * The spinner occasions (themes/spinnerSets.ts) recommended for each kind of group, the keys of the platform's starter sets (cultural, religious, band, charity); the rest are "Other available"
 * on the card. A square from before kinds of group counts as cultural. The festival set goes with cultural and religious groups. My call (W18-R29), to confirm.
 */
export const SPINNER_RECOMMENDED: Record<string, string[]> = {
  cultural: ['Festivals', 'Cultural'],
  religious: ['Festivals', 'Religious'],
  band: ['Bands & Artists'],
  charity: ['Charity & Donations'],
}

/**
 * The shape choices (W18 shapes steps 2 to 7): per part a short list of named options. The ids are equal to square/frontend/src/themes/shapes.ts and to SHAPE_OPTIONS in
 * backend/app/platform/theme_overrides.py (tests compare them). `radius` and `frame` only draw the small picture on the chip; the real corners are set in the square app.
 */
export type ShapePartId = 'buttons' | 'cards' | 'photos' | 'edges'
export interface ShapeOption { id: string; label: string; radius: string; edge?: string }
export const SHAPE_PARTS: { id: ShapePartId; options: ShapeOption[] }[] = [
  { id: 'buttons', options: [{ id: 'square', label: 'Square', radius: '0' }, { id: 'soft', label: 'Soft', radius: '8px' }, { id: 'rounded', label: 'Rounded', radius: '10px' }, { id: 'pill', label: 'Pill', radius: '999px' }] },
  { id: 'cards', options: [{ id: 'square', label: 'Square', radius: '0' }, { id: 'soft', label: 'Soft', radius: '8px' }, { id: 'rounded', label: 'Rounded', radius: '18px' }] },
  { id: 'photos', options: [{ id: 'square', label: 'Square', radius: '0' }, { id: 'soft', label: 'Soft', radius: '8px' }, { id: 'rounded', label: 'Rounded', radius: '18px' }, { id: 'arch', label: 'Arch', radius: '999px 999px 0 0' }, { id: 'circle', label: 'Circle', radius: '50%' }] },
  { id: 'edges', options: [{ id: 'flat', label: 'Flat', radius: '6px', edge: 'none' }, { id: 'line', label: 'Thin line', radius: '6px', edge: '1px solid currentColor' }, { id: 'strong', label: 'Strong line', radius: '6px', edge: '2px solid currentColor' }, { id: 'shadow', label: 'Soft shadow', radius: '6px', edge: 'shadow' }] },
]
export type ShapeLookChoice = Partial<Record<ShapePartId, string>>

/**
 * The "Feel" choices (W18-R44): the default light or dark, whether the visitor's switch is shown, the density, the text size, the motion and the divider style. The ids are equal to square/frontend/src/themes/feel.ts and to
 * FEEL_OPTIONS in backend/app/platform/theme_overrides.py (tests compare them). A part not chosen is the theme as designed.
 */
export type FeelPartId = 'mode' | 'switch' | 'density' | 'text' | 'motion' | 'divider'
export interface FeelOption { id: string; label: string; hint: string }
export const FEEL_PARTS: { id: FeelPartId; options: FeelOption[] }[] = [
  { id: 'mode', options: [{ id: 'light', label: 'Light', hint: 'Always starts light' }, { id: 'dark', label: 'Dark', hint: 'Always starts dark' }, { id: 'system', label: 'Follow the device', hint: 'Light or dark as set on the device' }] },
  { id: 'switch', options: [{ id: 'show', label: 'Show the switch', hint: 'Visitors can change light or dark' }, { id: 'hide', label: 'Hide the switch', hint: 'Everyone sees your default' }] },
  { id: 'density', options: [{ id: 'compact', label: 'Compact', hint: 'Tighter spacing, more on a screen' }, { id: 'comfortable', label: 'Comfortable', hint: 'Balanced spacing' }, { id: 'airy', label: 'Airy', hint: 'Generous spacing' }] },
  { id: 'text', options: [{ id: 'normal', label: 'Normal', hint: 'The theme\'s own size' }, { id: 'large', label: 'Large', hint: '12 % bigger, easier to read' }, { id: 'xlarge', label: 'Extra large', hint: '25 % bigger, text and the space around it' }] },
  { id: 'motion', options: [{ id: 'lively', label: 'Lively', hint: 'Hover lift and moving strips, as the theme designed' }, { id: 'nolift', label: 'Still cards', hint: 'Cards and buttons do not lift on hover; strips keep moving' }, { id: 'nostrip', label: 'Still strips', hint: 'Scrolling strips stand still; cards still lift on hover' }, { id: 'calm', label: 'Calm', hint: 'No hover lift and the strips stand still' }] },
  { id: 'divider', options: [{ id: 'glyph', label: 'Ornament', hint: 'Lines with the small glyph between sections' }, { id: 'line', label: 'Plain line', hint: 'The lines without the glyph' }, { id: 'none', label: 'Nothing', hint: 'No divider between sections' }] },
]
export type FeelLookChoice = Partial<Record<FeelPartId, string>>

export interface Seeds { bg: string; ink: string; acc: string }

/** The page, text and accent colours of a theme in light mode (or dark, for a theme that opens dark), in the form the platform stores (bg, ink, acc), or null for an unknown theme. */
export function presetColours(themeId: string, mode: 'light' | 'dark' = 'light'): Seeds | null {
  const o = OWN_SCHEMES.find((x) => x.id === themeId)
  if (o) { const [bg, ink, acc] = mode === 'dark' ? o.d : o.l; return { bg, ink, acc } }
  const c = THEME_COLORS[themeId]?.[mode]
  return c ? { bg: c.bg.toLowerCase(), ink: c.ink.toLowerCase(), acc: c.accent.toLowerCase() } : null
}

export function isHex(v: string): boolean {
  return /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(v.trim())
}
