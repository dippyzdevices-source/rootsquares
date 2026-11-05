import { createApp } from 'vue'
import { createPinia } from 'pinia'
import AdminApp from './AdminApp.vue'
import { router } from './router'
import { i18n } from '@rootsquares/ui/i18n'
import adminEn from './i18n/admin.en.json'
import adminNo from './i18n/admin.no.json'
import { useStaffStore } from './stores/staff'
import { gateStart } from '@rootsquares/ui/gate/gate'
import { setEnvLabel } from '@rootsquares/ui/env/envLabel'
import { showBrandIcon } from '@rootsquares/ui/gate/brandHead'
// The same self-hosted fonts and styles as the customer app (ADR 083: one design system, two applications).
import '@rootsquares/ui/styles/fonts.css'
import '@rootsquares/ui/styles/main.css'
import './styles/number-font.css' // the digits of the big figures in Playfair Display (W26-R40)

// The admin wording is merged in here only: the customer app never loads it.
i18n.global.mergeLocaleMessage('en', adminEn)
i18n.global.mergeLocaleMessage('no', adminNo)

// A private (staging) deploy has a site gate (ADR 099): until this browser has its pass, only the passcode screen is shown. No gate = this check passes at once.
void (async () => {
  const apiBase = (import.meta.env.VITE_ADMIN_API_BASE_URL as string | undefined) ?? 'http://localhost:5001'
  const gate = await gateStart(apiBase)
  setEnvLabel(gate.env) // the environment strip (W26-R25), display only
  if (!gate.open) {
    const { default: GateScreen } = await import('@rootsquares/ui/components/GateScreen.vue')
    createApp(GateScreen, { base: apiBase, onOpen: () => window.location.reload() }).use(i18n).mount('#app')
    return
  }
  showBrandIcon() // the page shell is neutral until the gate is open (W27-R32)
  start()
})()

function start() {
  const pinia = createPinia()
  const app = createApp(AdminApp).use(pinia).use(router).use(i18n)

  // A request answered 401 after the sign-in (idle too long, signed out elsewhere, account switched off) sends the person back to the sign-in page.
  window.addEventListener('admin-signed-out', () => {
    useStaffStore(pinia).clear()
    void router.push('/sign-in')
  })
  router.afterEach((to) => {
    const key = typeof to.meta.titleKey === 'string' ? to.meta.titleKey : ''
    const t = i18n.global.t
    // The tab title starts with the word Admin (W26-R23): with many tabs open only the first words show, and they say where you are.
    const tag = t('portal.adminTag')
    document.title = key ? `${tag} · ${t(key)} · ${t('app.name')}` : `${tag} · ${t('app.name')}`
  })
  app.mount('#app')
}
