import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { i18n } from '@rootsquares/ui/i18n'
import platformEn from './i18n/en.json'
import platformNo from './i18n/no.json'
import { isSquareHost, squareAppRedirect } from './services/hostMode'
import { gateStart } from '@rootsquares/ui/gate/gate'
import { setEnvLabel } from '@rootsquares/ui/env/envLabel'
import { showBrandIcon } from '@rootsquares/ui/gate/brandHead'
import { captureReferral } from './services/referral'
import './styles/spinner-sets.css'
// Self-hosted platform fonts (no network calls): one file in the ui package, shared with the admin application.
import '@rootsquares/ui/styles/fonts.css'
import './styles/main.css'

// The customer wording that the shared messages (ui) do not carry: merged here only, the admin application never loads it.
i18n.global.mergeLocaleMessage('en', platformEn)
i18n.global.mergeLocaleMessage('no', platformNo)

// On a square's own host name (<slug>.localhost, a square domain) only the square site is mounted, without the platform router and stores.
void (async () => {
  const squareApp = squareAppRedirect() // <slug>.localhost on the platform's dev server: the real square site is the square app
  if (squareApp) {
    window.location.replace(squareApp)
    return
  }
  // A private (staging) deploy has a site gate (ADR 099): until this browser has its pass, only the passcode screen is shown. No gate = this check passes at once.
  const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:5001'
  const start = await gateStart(apiBase)
  setEnvLabel(start.env) // the environment strip (W26-R25), display only
  if (!start.open) {
    const { default: GateScreen } = await import('@rootsquares/ui/components/GateScreen.vue')
    createApp(GateScreen, { base: apiBase, onOpen: () => window.location.reload() }).use(i18n).mount('#app')
    return
  }
  showBrandIcon() // the page shell is neutral until the gate is open (W27-R32)
  document.title = i18n.global.t('app.name')
  if (isSquareHost) {
    const { default: SquareSiteRoot } = await import('./features/platform/SquareSiteRoot.vue')
    createApp(SquareSiteRoot).use(i18n).mount('#app')
  } else {
    captureReferral() // a referral link (?ref=CODE) is remembered for the voucher box (W14-R27)
    // A tab title per page (W26-R23): the page, then the name; the admin application's tabs start with Admin instead.
    router.afterEach((to) => {
      const key = typeof to.meta.titleKey === 'string' ? to.meta.titleKey : ''
      document.title = key ? `${i18n.global.t(key)} · ${i18n.global.t('app.name')}` : i18n.global.t('app.name')
    })
    createApp(App).use(createPinia()).use(router).use(i18n).mount('#app')
  }
})()
