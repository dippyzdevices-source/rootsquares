import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { DEFAULT_TENANT_THEME, isThemeId } from '@rootsquares/ui/themes'
import { guardRedirect } from '@/auth/roles'
import { useAuthStore } from '@/stores/auth'
import { marketingRoutes } from '@/features/marketing/routes'
import { onboardingRoutes } from '@/features/onboarding/routes'
import { tenantSiteRoutes } from '@/features/tenant-site/routes'
import { portalRoutes, themeStudioRoute, invoiceRoute } from '@/features/portal/routes'

const routes: RouteRecordRaw[] = [
  marketingRoutes,
  themeStudioRoute,
  invoiceRoute,
  portalRoutes,
  onboardingRoutes,
  tenantSiteRoutes,
  { path: '/s/:slug', name: 'square-hello', component: () => import('@/features/platform/SquareHelloView.vue'), props: true, meta: { titleKey: 'pages.squareHello' } },
  { path: '/site', redirect: `/site/${DEFAULT_TENANT_THEME}` },
  {
    path: '/:pathMatch(.*)*',
    component: () => import('@/layouts/PlatformLayout.vue'),
    children: [{ path: '', name: 'not-found', component: () => import('@/features/marketing/NotFoundView.vue'), meta: { titleKey: 'common.notFound' } }],
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: (to, _from, saved) => saved ?? (to.hash ? { el: to.hash, top: 68, behavior: 'smooth' } : { top: 0 }),
})

// Session guard: ask the server once who is signed in, then apply the role rules in src/auth/roles.ts.
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.load()
  const redirect = guardRedirect({ role: auth.role, square: null, needsOrg: auth.needsOrg }, to.path)
  if (redirect && redirect !== to.path) return { path: redirect, replace: true }
})

router.beforeEach((to) => {
  const themeId = to.params.themeId
  if (to.path.startsWith('/site/') && !isThemeId(themeId)) {
    return { path: `/site/${DEFAULT_TENANT_THEME}`, replace: true }
  }
})
