/**
 * What it is:   The Google Fonts catalogue of the font picker (rootsquares W25-R63): about 1,975 families with category, weights and the scripts they cover besides Latin.
 * What it does: loadCatalogue() fetches `googleFonts.json` on first use (a separate chunk, so the page is not heavier for an owner who never opens the picker); searchFonts() filters by
 *               text, category and script; resolveFace() turns a family into the {f, c, w} the platform sends (the server checks the family and recomputes category and weights, the same rule:
 *               the weights nearest to 400 and 700); ACCENT_CHOICES is the short list of accent fonts, equal to ACCENTS of the square app and ACCENT_IDS of the server (a test compares).
 * How to use:   const fonts = await loadCatalogue(); searchFonts(fonts, { q: 'serif', category: 'serif', script: 'devanagari' }, 60); resolveFace(fonts, 'Lora').
 * Run:          npm run test:look (from frontend/) compares the list with the server's copy and the accent ids.
 * Read before:  scripts/build_google_fonts.py (makes googleFonts.json and the server's copy), docs/reference/fonts.md (licences).
 * Read after:   features/portal/FontPicker.vue, features/portal/ThemeLookCard.vue.
 */
export interface GoogleFont { f: string; c: string; w: number[]; s: string[] }
export interface FontFace { f: string; c: string; w: number[] }
export interface FontQuery { q: string; category: string; script: string }

let catalogue: Promise<GoogleFont[]> | null = null

export function loadCatalogue(): Promise<GoogleFont[]> {
  catalogue ??= import('./googleFonts.json').then((m) => (m.default as unknown as [string, string, number[], string[]][]).map(([f, c, w, s]) => ({ f, c, w, s })))
  return catalogue
}

export const FONT_CATEGORIES = ['serif', 'sans-serif', 'display', 'handwriting', 'monospace'] as const

/** The scripts worth a filter, in the order shown; the catalogue lists more (Latin is every font's). */
export const FONT_SCRIPTS = ['cyrillic', 'greek', 'vietnamese', 'devanagari', 'bengali', 'tamil', 'telugu', 'gujarati', 'gurmukhi', 'kannada', 'malayalam', 'arabic', 'hebrew', 'thai', 'japanese', 'korean', 'chinese-simplified', 'chinese-traditional'] as const

export function searchFonts(all: GoogleFont[], query: FontQuery, limit: number): { shown: GoogleFont[]; total: number } {
  const q = query.q.trim().toLowerCase()
  const hits = all.filter((x) => (!q || x.f.toLowerCase().includes(q)) && (!query.category || x.c === query.category) && (!query.script || x.s.includes(query.script)))
  return { shown: hits.slice(0, limit), total: hits.length }
}

const nearest = (available: number[], target: number) => available.reduce((best, w) => (Math.abs(w - target) < Math.abs(best - target) || (Math.abs(w - target) === Math.abs(best - target) && w < best) ? w : best), available[0]!)

/** The face the platform sends for a chosen family (heading and body alike: weights nearest to 400 and 700). */
export function resolveFace(font: GoogleFont): FontFace {
  return { f: font.f, c: font.c, w: [...new Set([nearest(font.w, 400), nearest(font.w, 700)])].sort((a, b) => a - b) }
}

/** The accent lines: ids equal to the square app (`ACCENTS`) and the server (`ACCENT_IDS`); `headings` follows the heading font. */
export const ACCENT_CHOICES: { id: string; label: string }[] = [
  { id: 'sacramento', label: 'Sacramento' },
  { id: 'dancing', label: 'Dancing Script' },
  { id: 'caveat', label: 'Caveat' },
  { id: 'great-vibes', label: 'Great Vibes' },
  { id: 'headings', label: 'Same as the headings' },
]
