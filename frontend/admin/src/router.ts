import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { adminRoutes } from './routes'
import { useStaffStore } from './stores/staff'

// The admin application's router. Everything but the three sign-in pages needs a finished sign-in (password and second step); the guard sends the person
// to the page for the step they are at. Nothing of the customer app is in here.
const SIGN_IN_PAGES = ['/sign-in', '/second-step', '/set-up']
const routes: RouteRecordRaw[] = [
  {
    // The three sign-in pages share the frame of the customer app's sign-in (no site header or footer). The parent has its own path so it can never
    // match the console's '/'; the children after the first have absolute paths.
    path: '/sign-in',
    component: () => import('./layouts/SignInLayout.vue'),
    children: [
      { path: '', name: 'sign-in', component: () => import('./views/AdminSignInView.vue'), meta: { titleKey: 'adm.signIn.title' } },
      { path: '/second-step', name: 'second-step', component: () => import('./views/AdminSecondStepView.vue'), meta: { titleKey: 'adm.second.title' } },
      { path: '/set-up', name: 'set-up', component: () => import('./views/AdminEnrolView.vue'), meta: { titleKey: 'adm.enrol.title' } },
    ],
  },
  adminRoutes,
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({ history: createWebHistory(), routes, scrollBehavior: () => ({ top: 0 }) })

router.beforeEach(async (to) => {
  const staff = useStaffStore()
  await staff.load()
  const want = staff.step === null ? '/sign-in' : staff.step === 'totp' ? '/second-step' : staff.step === 'enrol' ? '/set-up' : null
  if (want) return to.path === want ? true : { path: want, replace: true }
  if (SIGN_IN_PAGES.includes(to.path)) return { path: '/', replace: true } // signed in already
  return true
})
