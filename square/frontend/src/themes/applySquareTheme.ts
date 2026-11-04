import { LAYOUT_THEME_FONT_URLS } from './layoutThemeFonts'

/**
 * Makes the site follow the square's theme (rootsquares W6-R50). The default theme (paper-brick) is bca-oslo's own look, so it sets nothing;
 * any other known theme sets data-square-theme on <html> (src/styles/square-theme-map.css maps its --t-* values onto the --ds-* tokens) and loads
 * that theme's fonts once (the address comes from layoutThemeFonts.ts, generated from the design files). An unknown id changes nothing.
 */
export function squareThemeFontsUrl(themeId: string): string | null {
  return LAYOUT_THEME_FONT_URLS[themeId] ?? null
}

export function applySquareTheme(themeId: string, doc: Document = document): boolean {
  const url = squareThemeFontsUrl(themeId)
  if (!url) return false
  doc.documentElement.dataset.squareTheme = themeId
  if (!doc.querySelector('link[data-square-theme-fonts]')) {
    const link = doc.createElement('link')
    link.rel = 'stylesheet'
    link.href = url
    link.dataset.squareThemeFonts = themeId
    doc.head.appendChild(link)
  }
  return true
}
