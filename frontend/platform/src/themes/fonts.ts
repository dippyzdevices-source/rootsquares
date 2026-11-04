// Self-hosted tenant theme fonts (@fontsource woff2, latin + latin-ext). Generated from the weights in design/tenant-themes-v2/tokens/fonts.css.
// Each theme loads its own fonts only when it becomes active (dynamic import, code-split). Licences: docs/reference/fonts.md. Dark variants share the light fonts.
type Loader = () => Promise<unknown>
const SETS: Record<string, Loader[]> = {
  'paper-brick': [
    () => import('@fontsource/marcellus/latin-400.css'),
    () => import('@fontsource/marcellus/latin-ext-400.css'),
    () => import('@fontsource/karla/latin-400.css'),
    () => import('@fontsource/karla/latin-ext-400.css'),
    () => import('@fontsource/karla/latin-600.css'),
    () => import('@fontsource/karla/latin-ext-600.css'),
    () => import('@fontsource/karla/latin-700.css'),
    () => import('@fontsource/karla/latin-ext-700.css'),
  ],
  'harvest-hall': [
    () => import('@fontsource/dm-serif-display/latin-400.css'),
    () => import('@fontsource/dm-serif-display/latin-ext-400.css'),
    () => import('@fontsource/dm-sans/latin-400.css'),
    () => import('@fontsource/dm-sans/latin-ext-400.css'),
    () => import('@fontsource/dm-sans/latin-600.css'),
    () => import('@fontsource/dm-sans/latin-ext-600.css'),
    () => import('@fontsource/dm-sans/latin-700.css'),
    () => import('@fontsource/dm-sans/latin-ext-700.css'),
  ],
  'stillwater': [
    () => import('@fontsource/cormorant-garamond/latin-500.css'),
    () => import('@fontsource/cormorant-garamond/latin-ext-500.css'),
    () => import('@fontsource/cormorant-garamond/latin-600.css'),
    () => import('@fontsource/cormorant-garamond/latin-ext-600.css'),
    () => import('@fontsource/mulish/latin-400.css'),
    () => import('@fontsource/mulish/latin-ext-400.css'),
    () => import('@fontsource/mulish/latin-600.css'),
    () => import('@fontsource/mulish/latin-ext-600.css'),
    () => import('@fontsource/mulish/latin-700.css'),
    () => import('@fontsource/mulish/latin-ext-700.css'),
  ],
  'fjord-modern': [
    () => import('@fontsource/sora/latin-500.css'),
    () => import('@fontsource/sora/latin-ext-500.css'),
    () => import('@fontsource/sora/latin-600.css'),
    () => import('@fontsource/sora/latin-ext-600.css'),
    () => import('@fontsource/sora/latin-700.css'),
    () => import('@fontsource/sora/latin-ext-700.css'),
    () => import('@fontsource/work-sans/latin-400.css'),
    () => import('@fontsource/work-sans/latin-ext-400.css'),
    () => import('@fontsource/work-sans/latin-600.css'),
    () => import('@fontsource/work-sans/latin-ext-600.css'),
  ],
  'pencil-club': [
    () => import('@fontsource/bricolage-grotesque/latin-600.css'),
    () => import('@fontsource/bricolage-grotesque/latin-ext-600.css'),
    () => import('@fontsource/bricolage-grotesque/latin-700.css'),
    () => import('@fontsource/bricolage-grotesque/latin-ext-700.css'),
    () => import('@fontsource/bricolage-grotesque/latin-800.css'),
    () => import('@fontsource/bricolage-grotesque/latin-ext-800.css'),
    () => import('@fontsource/figtree/latin-400.css'),
    () => import('@fontsource/figtree/latin-ext-400.css'),
    () => import('@fontsource/figtree/latin-600.css'),
    () => import('@fontsource/figtree/latin-ext-600.css'),
    () => import('@fontsource/figtree/latin-700.css'),
    () => import('@fontsource/figtree/latin-ext-700.css'),
  ],
  'olive-linen': [
    () => import('@fontsource/libre-baskerville/latin-400.css'),
    () => import('@fontsource/libre-baskerville/latin-ext-400.css'),
    () => import('@fontsource/libre-baskerville/latin-700.css'),
    () => import('@fontsource/libre-baskerville/latin-ext-700.css'),
    () => import('@fontsource/source-sans-3/latin-400.css'),
    () => import('@fontsource/source-sans-3/latin-ext-400.css'),
    () => import('@fontsource/source-sans-3/latin-600.css'),
    () => import('@fontsource/source-sans-3/latin-ext-600.css'),
    () => import('@fontsource/source-sans-3/latin-700.css'),
    () => import('@fontsource/source-sans-3/latin-ext-700.css'),
  ],
  'berry-courtyard': [
    () => import('@fontsource/young-serif/latin-400.css'),
    () => import('@fontsource/young-serif/latin-ext-400.css'),
    () => import('@fontsource/hanken-grotesk/latin-400.css'),
    () => import('@fontsource/hanken-grotesk/latin-ext-400.css'),
    () => import('@fontsource/hanken-grotesk/latin-600.css'),
    () => import('@fontsource/hanken-grotesk/latin-ext-600.css'),
    () => import('@fontsource/hanken-grotesk/latin-700.css'),
    () => import('@fontsource/hanken-grotesk/latin-ext-700.css'),
  ],
  'atrium': [
    () => import('@fontsource/instrument-serif/latin-400.css'),
    () => import('@fontsource/instrument-serif/latin-ext-400.css'),
    () => import('@fontsource/instrument-sans/latin-400.css'),
    () => import('@fontsource/instrument-sans/latin-ext-400.css'),
    () => import('@fontsource/instrument-sans/latin-600.css'),
    () => import('@fontsource/instrument-sans/latin-ext-600.css'),
    () => import('@fontsource/instrument-sans/latin-700.css'),
    () => import('@fontsource/instrument-sans/latin-ext-700.css'),
  ],
  'ledger': [
    () => import('@fontsource/schibsted-grotesk/latin-500.css'),
    () => import('@fontsource/schibsted-grotesk/latin-ext-500.css'),
    () => import('@fontsource/schibsted-grotesk/latin-700.css'),
    () => import('@fontsource/schibsted-grotesk/latin-ext-700.css'),
    () => import('@fontsource/newsreader/latin-400.css'),
    () => import('@fontsource/newsreader/latin-ext-400.css'),
    () => import('@fontsource/newsreader/latin-600.css'),
    () => import('@fontsource/newsreader/latin-ext-600.css'),
  ],
  'marquee': [
    () => import('@fontsource/playfair-display/latin-600.css'),
    () => import('@fontsource/playfair-display/latin-ext-600.css'),
    () => import('@fontsource/playfair-display/latin-700.css'),
    () => import('@fontsource/playfair-display/latin-ext-700.css'),
    () => import('@fontsource/outfit/latin-400.css'),
    () => import('@fontsource/outfit/latin-ext-400.css'),
    () => import('@fontsource/outfit/latin-600.css'),
    () => import('@fontsource/outfit/latin-ext-600.css'),
    () => import('@fontsource/outfit/latin-700.css'),
    () => import('@fontsource/outfit/latin-ext-700.css'),
  ],
}

const loaded = new Set<string>()

/** Loads the fonts of a tenant theme once. System fallbacks in themes.css apply until they arrive. */
export function loadThemeFonts(themeId: string): Promise<void> {
  const id = themeId.replace(/-dark$/, '')
  const set = SETS[id]
  if (!set || loaded.has(id)) return Promise.resolve()
  loaded.add(id)
  return Promise.all(set.map((l) => l())).then(() => undefined, () => { loaded.delete(id) })
}
