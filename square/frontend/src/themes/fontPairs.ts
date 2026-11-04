/**
 * What it is:   The font pairs an owner can choose for a square's public site (rootsquares W18, docs/plans/themes-dynamic-plan.md, step 3; owner's decision W18-R14: about 12 pairs from fonts the 56 themes already use).
 * What it does: Lists 23 pairs (display + body; the first 14 from the themes, the last 9 added in W19-R12 from the Font Pairings design) with the Google Fonts address of each, for the first 14 taken unchanged from the theme that uses the pair in design/tenant-themes-v7/themes.json;
 *               fontStack() builds the CSS font-family value. fontPairs.spec.ts checks every pair against themes.json so the list cannot drift.
 * How to use:   import { FONT_PAIRS, fontPairById, fontStack }. Applying a pair to the page is done by applyThemeOverrides.ts.
 * Run:          from square/frontend: npx vitest run src/themes/fontPairs.spec.ts
 * Read before:  docs/reference/fonts.md (licences: all OFL), src/themes/layoutThemeFonts.ts (the per-theme addresses, generated).
 * Read after:   src/themes/applyThemeOverrides.ts.
 */
export interface FontPair {
  id: string
  label: string
  display: string
  body: string
  /** The display face is a serif: the fallback stack ends in Georgia, serif. */
  serif: boolean
  /** The heaviest display weight the stylesheet loads, so the browser never fakes a bold. */
  displayWeight: number
  url: string
}

const g = (q: string) => `https://fonts.googleapis.com/css2?${q}&display=swap`

export const FONT_PAIRS: FontPair[] = [
  { id: 'classic', label: 'Classic', display: 'Marcellus', body: 'Karla', serif: true, displayWeight: 400, url: g('family=Marcellus&family=Karla:wght@400;600;700') },
  { id: 'friendly', label: 'Friendly modern', display: 'Bricolage Grotesque', body: 'Figtree', serif: false, displayWeight: 700, url: g('family=Bricolage+Grotesque:wght@500;600;700;800&family=Figtree:wght@400;500;600;700') },
  { id: 'editorial', label: 'Editorial serif', display: 'DM Serif Display', body: 'DM Sans', serif: true, displayWeight: 400, url: g('family=DM+Serif+Display&family=DM+Sans:wght@400;500;600;700') },
  { id: 'elegant', label: 'Elegant', display: 'Cormorant Garamond', body: 'Mulish', serif: true, displayWeight: 600, url: g('family=Cormorant+Garamond:wght@500;600&family=Mulish:wght@400;600;700') },
  { id: 'clean', label: 'Clean and clear', display: 'Sora', body: 'Work Sans', serif: false, displayWeight: 700, url: g('family=Sora:wght@500;600;700&family=Work+Sans:wght@400;600') },
  { id: 'dramatic', label: 'High contrast', display: 'Playfair Display', body: 'Karla', serif: true, displayWeight: 700, url: g('family=Playfair+Display:wght@600;700;800&family=Karla:wght@400;500;600;700') },
  { id: 'warm', label: 'Warm serif', display: 'Lora', body: 'Nunito Sans', serif: true, displayWeight: 700, url: g('family=Lora:wght@500;600;700&family=Nunito+Sans:wght@400;600;700') },
  { id: 'soft', label: 'Soft and rounded', display: 'Quicksand', body: 'Nunito', serif: false, displayWeight: 700, url: g('family=Quicksand:wght@500;600;700&family=Nunito:wght@400;600;700') },
  { id: 'bold', label: 'Bold geometric', display: 'Space Grotesk', body: 'Public Sans', serif: false, displayWeight: 700, url: g('family=Space+Grotesk:wght@500;600;700&family=Public+Sans:wght@400;500;600;700') },
  { id: 'playful', label: 'Playful', display: 'Fredoka', body: 'Albert Sans', serif: false, displayWeight: 600, url: g('family=Fredoka:wght@500;600&family=Albert+Sans:wght@400;600;700') },
  { id: 'contemporary', label: 'Contemporary', display: 'Instrument Serif', body: 'Instrument Sans', serif: true, displayWeight: 400, url: g('family=Instrument+Serif&family=Instrument+Sans:wght@400;600;700') },
  { id: 'scholarly', label: 'Traditional', display: 'Libre Baskerville', body: 'Source Sans 3', serif: true, displayWeight: 700, url: g('family=Libre+Baskerville:wght@400;700&family=Source+Sans+3:wght@400;600;700') },
  { id: 'sturdy', label: 'Warm and sturdy', display: 'Young Serif', body: 'Hanken Grotesk', serif: true, displayWeight: 400, url: g('family=Young+Serif&family=Hanken+Grotesk:wght@400;600;700') },
  { id: 'newsroom', label: 'Newsroom', display: 'Schibsted Grotesk', body: 'Newsreader', serif: false, displayWeight: 700, url: g('family=Schibsted+Grotesk:wght@500;700&family=Newsreader:wght@400;600') },
  { id: 'display', label: 'Bold display', display: 'Gloock', body: 'Manrope', serif: true, displayWeight: 400, url: g('family=Gloock&family=Manrope:wght@400;600;700') },
  { id: 'gallery', label: 'Gallery', display: 'Syne', body: 'Outfit', serif: false, displayWeight: 700, url: g('family=Syne:wght@600;700&family=Outfit:wght@400;600;700') },
  { id: 'futuristic', label: 'Futuristic friendly', display: 'Unbounded', body: 'Plus Jakarta Sans', serif: false, displayWeight: 500, url: g('family=Unbounded:wght@500;600&family=Plus+Jakarta+Sans:wght@400;600;700') },
  { id: 'fashion', label: 'Fashion contrast', display: 'Bodoni Moda', body: 'Jost', serif: true, displayWeight: 500, url: g('family=Bodoni+Moda:wght@500;600&family=Jost:wght@400;600;700') },
  { id: 'sansoverserif', label: 'Sans over serif', display: 'Epilogue', body: 'Source Serif 4', serif: false, displayWeight: 700, url: g('family=Epilogue:wght@600;700&family=Source+Serif+4:wght@400;600;700') },
  { id: 'quirky', label: 'Quirky grotesque', display: 'Familjen Grotesk', body: 'Literata', serif: false, displayWeight: 600, url: g('family=Familjen+Grotesk:wght@500;600&family=Literata:wght@400;600;700') },
  { id: 'refined', label: 'Refined classic', display: 'Libre Caslon Text', body: 'Albert Sans', serif: true, displayWeight: 400, url: g('family=Libre+Caslon+Text&family=Albert+Sans:wght@400;600;700') },
  { id: 'upbeat', label: 'Playful and bold', display: 'Gabarito', body: 'Nunito Sans', serif: false, displayWeight: 600, url: g('family=Gabarito:wght@500;600&family=Nunito+Sans:wght@400;600;700') },
  { id: 'literary', label: 'Soft literary', display: 'Newsreader', body: 'Hanken Grotesk', serif: true, displayWeight: 400, url: g('family=Newsreader:wght@400;500&family=Hanken+Grotesk:wght@400;600;700') },
]

export function fontPairById(id: string | null | undefined): FontPair | null {
  return FONT_PAIRS.find((p) => p.id === id) ?? null
}

export function fontStack(name: string, serif: boolean): string {
  return `"${name}",` + (serif ? 'Georgia,serif' : '"Helvetica Neue",Arial,sans-serif')
}
