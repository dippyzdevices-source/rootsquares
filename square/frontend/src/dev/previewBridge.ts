// Lets the platform's Theme page show this site inside an iframe and switch light or dark in it (W10-R13, W10-R14). The platform sends 'rs-preview-hello' once
// the frame has loaded and this answers 'rs-preview-ready', so the platform knows the live site is really here (otherwise it shows its sketch).
// 'rs-preview-mode' toggles the dark class without storing anything. 'rs-preview-look' {colors, fonts, shape, feel} shows the owner's own colours, font pair, shapes and feel (W18-R19) without storing anything;
// every value is checked again by themes/applyThemeOverrides.ts, and both null removes the look.
// - Development, a real square: only a parent on localhost or 127.0.0.1 is listened to (`?theme=<id>` shows the square's own data).
// - Demo mode (any build): any parent may ask. The demo holds no data and the messages only say hello and light or dark.
// - Otherwise (a real square in a production build) it is never installed. Inert when the site is not in a frame.
import { demoActive } from '../demo/install'
import { opensDark } from '../layout-themes/layouts'
import { squareProfile } from '../services/squareConfig'
import { applyThemeOverrides, type ThemeOverrides } from '../themes/applyThemeOverrides'
import { useTheme } from '../composables/useTheme'
import { cleanFeel, type FeelChoice } from '../themes/feel'
import { cleanShape, type ShapeChoice } from '../themes/shapes'
import { cleanType } from '../themes/customFonts'

let hadMode = false
const LOCAL_PARENT = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/

/** The look in a 'rs-preview-look' message, kept to the shapes the application accepts (strings only); null when it carries nothing. */
export function lookOf(d: { colors?: unknown; colors_dark?: unknown; fonts?: unknown; shape?: unknown; feel?: unknown; type?: unknown }): ThemeOverrides | null {
  const three = (v: unknown) => { const c = v as Record<string, unknown> | null | undefined; return c && typeof c === 'object' && typeof c.bg === 'string' && typeof c.ink === 'string' && typeof c.acc === 'string' ? { bg: c.bg, ink: c.ink, acc: c.acc } : null }
  const colors = three(d.colors)
  const colorsDark = three(d.colors_dark)
  const fonts = typeof d.fonts === 'string' ? d.fonts : null
  const shape = cleanShape(d.shape as ShapeChoice | null | undefined)
  const feel = cleanFeel(d.feel as FeelChoice | null | undefined)
  const type = cleanType(d.type)
  return colors || colorsDark || fonts || shape || feel || type ? { colors, fonts, ...(colorsDark ? { colors_dark: colorsDark } : {}), ...(shape ? { shape } : {}), ...(feel ? { feel } : {}), ...(type ? { type } : {}) } : null
}

export function installPreviewBridge(): void {
  if (typeof window === 'undefined' || window.parent === window) return
  const demo = demoActive()
  if (!demo && !import.meta.env.DEV) return
  window.addEventListener('message', (e: MessageEvent) => {
    if (e.source !== window.parent || (!demo && !LOCAL_PARENT.test(e.origin))) return
    const d = e.data as { type?: string; mode?: string; colors?: unknown; colors_dark?: unknown; fonts?: unknown; shape?: unknown; feel?: unknown; font_type?: unknown } | null
    if (d?.type === 'rs-preview-hello') (e.source as Window).postMessage({ type: 'rs-preview-ready' }, e.origin)
    else if (d?.type === 'rs-preview-mode') document.documentElement.classList.toggle('dark', d.mode === 'dark')
    else if (d?.type === 'rs-preview-look') {
      const look = lookOf({ ...d, type: d.font_type }) // the message's own `type` names the kind of message, so the fonts travel as `font_type`
      applyThemeOverrides(look, document, opensDark(squareProfile.themeId) ? 'dark' : 'light')
      // the owner's default mode of the draft; only when the draft has one (or just lost it), so the platform's own Light/Dark switch is not reset by every other change
      if (look?.feel?.mode || hadMode) useTheme().initTheme(look?.feel ?? null)
      hadMode = !!look?.feel?.mode
    }
  })
}
