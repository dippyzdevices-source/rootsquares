import type { RouteRecordRaw } from 'vue-router'

// The pages of the admin console (what used to live under /owner in the customer app). Paths are the admin application's own.
export const adminRoutes: RouteRecordRaw = {
  path: '/',
  component: () => import('./layouts/AdminLayout.vue'),
  children: [
    { path: '', name: 'overview', component: () => import('./features/OwnerOverviewView.vue'), meta: { titleKey: 'pages.owner' } },
    { path: 'attention', name: 'attention', component: () => import('./features/OwnerAttentionView.vue'), meta: { titleKey: 'own.attention.title' } },
    { path: 'squares', name: 'squares', component: () => import('./features/OwnerView.vue'), meta: { titleKey: 'pages.ownerSquares' } },
    { path: 'squares/:id', name: 'square', component: () => import('./features/OwnerSquareView.vue'), meta: { titleKey: 'pages.ownerSquare' } },
    { path: 'people', name: 'people', component: () => import('./features/OwnerPeopleView.vue'), meta: { titleKey: 'pages.ownerPeople' } },
    { path: 'people/:id', name: 'person', component: () => import('./features/OwnerPersonView.vue'), meta: { titleKey: 'pages.ownerPerson' } },
    { path: 'organisations', name: 'organisations', component: () => import('./features/OwnerOrganisationsView.vue'), meta: { titleKey: 'pages.ownerOrganisations' } },
    { path: 'health', name: 'health', component: () => import('./features/OwnerHealthView.vue'), meta: { titleKey: 'pages.ownerHealth' } },
    { path: 'audit', name: 'audit', component: () => import('./features/OwnerAuditView.vue'), meta: { titleKey: 'pages.ownerAudit' } },
    { path: 'prices', name: 'prices', component: () => import('./features/OwnerPricesView.vue'), meta: { titleKey: 'pages.ownerPrices' } },
    { path: 'opex', name: 'opex', component: () => import('./features/OwnerOpexView.vue'), meta: { titleKey: 'pages.ownerOpex' } },
    { path: 'vouchers', name: 'vouchers', component: () => import('./features/OwnerVouchersView.vue'), meta: { titleKey: 'pages.ownerVouchers' } },
    { path: 'support', name: 'support', component: () => import('./features/OwnerSupportView.vue'), meta: { titleKey: 'own.support.title' } },
    { path: 'prospects', name: 'prospects', component: () => import('./features/OwnerProspectsView.vue'), meta: { titleKey: 'pages.ownerProspects' } },
    { path: 'security', name: 'security', component: () => import('./views/AdminSecurityView.vue'), meta: { titleKey: 'adm.security.title' } },
    { path: 'subscriptions', name: 'subscriptions', component: () => import('./features/OwnerSubscriptionsView.vue'), meta: { titleKey: 'pages.ownerSubscriptions' } },
  ],
}
