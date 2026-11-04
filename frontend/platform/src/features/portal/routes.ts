import type { RouteRecordRaw } from 'vue-router'

// The platform portal (square owner): header and side bar of the portal shell, no marketing nav (design v4). Paths are the ones the pages always had;
// /squares/:id is the Dashboard of the square and its pages are the other six items of the portal nav.
export const portalRoutes: RouteRecordRaw = {
  path: '/',
  component: () => import('@/layouts/PortalLayout.vue'),
  children: [
    { path: 'dashboard', name: 'dashboard', component: () => import('@/features/platform/DashboardView.vue'), meta: { titleKey: 'pages.dashboard' } },
    { path: 'account', name: 'account', component: () => import('@/features/platform/AccountView.vue'), meta: { titleKey: 'pages.account' } },
    { path: 'billing/checkout', name: 'billing-checkout', component: () => import('./BillingCheckoutView.vue'), meta: { titleKey: 'portal.nav.billing' } },
    { path: 'organization/new', name: 'organization-new', component: () => import('@/features/platform/OrganizationView.vue'), meta: { titleKey: 'pages.organizationNew' } },
    { path: 'squares/new', name: 'square-new', component: () => import('@/features/platform/CreateSquareView.vue'), meta: { titleKey: 'pages.squareNew' } },
    {
      path: 'squares/:id',
      component: () => import('./SquareFrame.vue'),
      children: [
        { path: '', name: 'square', component: () => import('./SquareDashboardPage.vue'), meta: { titleKey: 'pages.square' } },
        { path: 'theme', name: 'square-theme', component: () => import('./SquareThemePage.vue'), meta: { titleKey: 'portal.nav.theme' } },
        { path: 'modules', name: 'square-modules', component: () => import('./SquareModulesPage.vue'), meta: { titleKey: 'portal.nav.modules' } },
        { path: 'health', name: 'square-health', component: () => import('./SquareHealthPage.vue'), meta: { titleKey: 'portal.nav.health' } },
        { path: 'analytics', name: 'square-analytics', component: () => import('./SquareAnalyticsPage.vue'), meta: { titleKey: 'portal.nav.analytics' } },
        { path: 'domain', name: 'square-domain', component: () => import('./SquareDomainPage.vue'), meta: { titleKey: 'portal.nav.domain' } },
        { path: 'payments', name: 'square-payments', component: () => import('./SquarePaymentsPage.vue'), meta: { titleKey: 'portal.nav.payments' } },
        { path: 'billing', name: 'square-billing', component: () => import('./SquareSoonPage.vue'), meta: { titleKey: 'portal.nav.billing', portalPage: 'billing' } },
        { path: 'settings', name: 'square-settings', component: () => import('./SquareSettingsPage.vue'), meta: { titleKey: 'portal.nav.settings' } },
        { path: 'support', name: 'square-support', component: () => import('./SquareSupportPage.vue'), meta: { titleKey: 'portal.nav.support' } },
      ],
    },
  ],
}

// The invoice of a paid payment (W19-R16): a printable A4 page on its own route, outside the portal shell like the studio.
export const invoiceRoute: RouteRecordRaw = {
  path: '/squares/:id/invoice/:orderId', name: 'square-invoice', component: () => import('./InvoicePage.vue'), meta: { titleKey: 'portal.invoice.title' },
}

// The Theme Studio (W19-R3): its own full-window route, outside the portal shell (no header, no side bar); the square is loaded by ThemeStudioFrame.
export const themeStudioRoute: RouteRecordRaw = {
  path: '/squares/:id/theme/studio',
  component: () => import('./ThemeStudioFrame.vue'),
  children: [{ path: '', name: 'square-theme-studio', component: () => import('./ThemeStudioPage.vue'), meta: { titleKey: 'portal.theme.studio.title' } }],
}
