/**
 * What it is:   The shape choices of the owner's own look: button corners, card corners, photo frames and edges (rootsquares W18, docs/plans/themes-shapes-plan.md, steps 2 to 4).
 * What it does: Lists the named options per part as data and builds the CSS for a choice. Buttons and cards set the corner variables the public pages read
 *               (`--t-radius-btn` and `--ds-radius-pill`; `--t-radius-*`, `--ds-radius-*` and `--lt-r`). Photo frames and edges are rules on the frame and card
 *               classes of the public pages (`.lt-photo`, `.ds-rect-inner`, `.ds-arch-inner`, `.ds-portrait-thumb`; `.ds-card` and the layout-theme cards) and use
 *               !important, because some themes set a corner inline or per theme. The admin and member console (.ds-appshell) keeps the design system's own look.
 *               A shape never changes colour or text size. `circle` makes people's pictures (committee, founders) round and the other photos rounded.
 * How to use:   shapeCss({ buttons: 'pill', cards: 'soft', photos: 'arch', edges: 'line' }) returns the CSS ('' when nothing valid is chosen);
 *               parseShape('buttons:pill,photos:arch') reads the `?shape=` preview text. Ids are kept equal to the backend list (backend/app/platform/theme_overrides.py).
 * Run:          from square/frontend: npx vitest run src/themes/shapes.spec.ts
 * Read before:  src/themes/applyThemeOverrides.ts (where it is written), src/styles/square-theme-map.css (the --ds-radius map).
 * Read after:   docs/plans/themes-shapes-plan.md.
 */

export interface ShapeChoice { buttons?: string | null; cards?: string | null; photos?: string | null; edges?: string | null }

/** Button corner radius per option. */
export const BUTTON_SHAPES: Record<string, string> = { square: '0px', soft: '8px', rounded: '14px', pill: '999px' }

/** Card corner radii per option: small, medium, large. */
export const CARD_SHAPES: Record<string, [string, string, string]> = {
  square: ['0px', '0px', '0px'],
  soft: ['4px', '8px', '12px'],
  rounded: ['8px', '14px', '22px'],
}

/** Photo frame corners per option: the radius of a picture, and of a person's picture (circle only). */
export const PHOTO_SHAPES: Record<string, { photo: string; person: string }> = {
  square: { photo: '0', person: '0' },
  soft: { photo: '8px', person: '8px' },
  rounded: { photo: '22px', person: '22px' },
  arch: { photo: '999px 999px 0 0', person: '999px 999px 0 0' },
  circle: { photo: '22px', person: '50%' },
}

/** Edge per option: border and shadow of cards and picture frames. */
export const EDGE_SHAPES: Record<string, { border: string; drop: string }> = {
  flat: { border: '0 solid transparent', drop: 'none' },
  line: { border: '1px solid var(--t-border, #d8d2c8)', drop: 'none' },
  strong: { border: '2px solid var(--t-text-strong, #222)', drop: 'none' },
  shadow: { border: '0 solid transparent', drop: '0 10px 28px -10px rgba(0, 0, 0, 0.28)' },
}

export const BUTTON_SHAPE_IDS = Object.keys(BUTTON_SHAPES)
export const CARD_SHAPE_IDS = Object.keys(CARD_SHAPES)
export const PHOTO_SHAPE_IDS = Object.keys(PHOTO_SHAPES)
export const EDGE_SHAPE_IDS = Object.keys(EDGE_SHAPES)

const PARTS = ['buttons', 'cards', 'photos', 'edges'] as const
const OPTIONS: Record<(typeof PARTS)[number], Record<string, unknown>> = { buttons: BUTTON_SHAPES, cards: CARD_SHAPES, photos: PHOTO_SHAPES, edges: EDGE_SHAPES }

/** Only the options that exist (a part that is not chosen is left out); anything else is dropped. Null when nothing valid is left. */
export function cleanShape(s: ShapeChoice | null | undefined): ShapeChoice | null {
  if (!s || typeof s !== 'object') return null
  const out: ShapeChoice = {}
  for (const p of PARTS) {
    const v = s[p]
    if (typeof v === 'string' && Object.prototype.hasOwnProperty.call(OPTIONS[p], v)) out[p] = v
  }
  return Object.keys(out).length ? out : null
}

// Where a picture frame or a card is drawn on the public pages; the console is left out.
const PHOTO_FRAMES = ['.lt-photo', '.ds-rect-inner', '.ds-arch-inner', '.ds-portrait-thumb']
const PERSON_FRAMES = ['.ds-portrait-thumb', '.ds-founder-portrait .ds-arch-inner']
const CARDS = ['.ds-card', '.lt-card', '.lt-rail-card', '.lt-pe-card', '.lt-sg-card', '.lt-pr-card', '.lt-co-card']
const PUBLIC = '.ds-scope.ds-scope'
const onPublic = (sels: string[]) => sels.map((s) => `html:root ${PUBLIC} ${s}:not(.ds-appshell ${s})`).join(',')

/** The CSS of a choice, or '' when nothing valid was asked. `html:root` puts it above the generated rules and the design system's, for paper-brick too. */
export function shapeCss(s: ShapeChoice | null | undefined): string {
  const c = cleanShape(s)
  if (!c) return ''
  const decl: string[] = []
  if (c.buttons) {
    const r = BUTTON_SHAPES[c.buttons]
    decl.push(`--t-radius-btn:${r};`, `--ds-radius-pill:${r};`)
  }
  if (c.cards) {
    const [sm, md, lg] = CARD_SHAPES[c.cards]
    decl.push(`--t-radius-sm:${sm};`, `--t-radius:${md};`, `--t-radius-lg:${lg};`, `--ds-radius-sm:${sm};`, `--ds-radius-md:${md};`, `--ds-radius-lg:${lg};`, `--lt-r:${lg};`)
  }
  const out: string[] = []
  if (decl.length) {
    out.push(`html:root ${PUBLIC}{${decl.join('')}}`)
    // the console keeps the design system's own corners, whatever the owner chose for the public pages
    out.push('html:root .ds-appshell.ds-appshell{--ds-radius-sm:6px;--ds-radius-md:10px;--ds-radius-lg:18px;--ds-radius-pill:999px;}')
  }
  if (c.photos) {
    const p = PHOTO_SHAPES[c.photos]
    out.push(`${onPublic(PHOTO_FRAMES)}{border-radius:${p.photo} !important;}`)
    out.push(`${onPublic(PERSON_FRAMES)}{border-radius:${p.person} !important;}`)
  }
  if (c.edges) {
    const e = EDGE_SHAPES[c.edges]
    out.push(`${onPublic([...CARDS, ...PHOTO_FRAMES])}{border:${e.border} !important;box-shadow:${e.drop} !important;}`)
  }
  return out.join('\n')
}

/** `buttons:pill,cards:soft` (the `?shape=` preview) to a choice; null when nothing valid is in it. */
export function parseShape(v: string | null | undefined): ShapeChoice | null {
  if (!v) return null
  const o: Record<string, string> = {}
  for (const part of v.split(',')) {
    const [k, val] = part.split(':').map((x) => x.trim())
    if ((PARTS as readonly string[]).includes(k) && val) o[k] = val
  }
  return cleanShape(o)
}

/** The choice as the `?shape=` text (for the kept preview). */
export function shapeText(s: ShapeChoice | null | undefined): string {
  const c = cleanShape(s)
  return c ? PARTS.filter((p) => c[p]).map((p) => `${p}:${c[p]}`).join(',') : ''
}
