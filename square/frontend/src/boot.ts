// The square site proper (W26-R20: this was main.ts; main.ts now asks the site gate first and loads this file only when the browser may see the site).
// demo/install and services/supportSession are imported by main.ts, before the gate check and before this file.
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import './styles/design-system.css'
import './styles/square-theme-map.css'
import './styles/square-layout-themes.css'
import './styles/theme-components.css'
import './styles/admin-type.css'
import './styles/spinner-sets.css'
import './layout-themes/layout-themes.css'
import './layout-themes/layout-themes-b.css'
import './layout-themes/layout-themes-c.css'
import './layout-themes/shell-parity.css'
import './layout-themes/japandi/japandi.css'
import App from './App.vue'
import { router } from './router'
import { useTheme } from './composables/useTheme'
import { squareProfile } from './services/squareConfig'
import { applySquareFavicon } from './utils/squareFavicon'
import { applySquareTheme } from './themes/applySquareTheme'
import { applyThemeOverrides, mergeOverrides, previewOverrides } from './themes/applyThemeOverrides'
import { opensDark } from './layout-themes/layouts'
import { installPreviewBridge } from './dev/previewBridge'

applySquareFavicon(squareProfile.name, squareProfile.logoUrl || squareProfile.logoDarkUrl) // the square's own tab icon (W6-R42)
applySquareTheme(squareProfile.themeId) // the square's own look (W6-R50)
let preview = null // own colours and fonts typed in the address: development and demo mode only
if (import.meta.env.MODE !== 'test' && (import.meta.env.DEV || new URLSearchParams(window.location.search).get('demo') === '1')) {
  try { preview = previewOverrides(window.location.search, window.sessionStorage) } catch { /* storage blocked: no preview */ }
}
const overrides = mergeOverrides(squareProfile.themeOverrides, preview) // squareProfile already holds the owner's shared draft for a visitor with the link (services/squareConfig.ts, W18-R47)
useTheme().initTheme(overrides?.feel) // light or dark: the owner's default (Feel tab) unless the visitor chose, else the theme's own rule
applyThemeOverrides(overrides, document, opensDark(squareProfile.themeId) ? 'dark' : 'light') // the owner's own look from the platform (W18-R18), the preview on top
installPreviewBridge() // the platform's live theme preview: development, and demo mode in any build (W10-R13, W10-R14)

// Auth initialization now happens inside the router's beforeEach guard (memoized, so it
// only really runs once) — every navigation, including the very first one, waits for
// real auth state before resolving. See router/index.ts and stores/auth.ts.
const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
