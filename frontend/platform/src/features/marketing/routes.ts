import type { RouteRecordRaw } from 'vue-router'

export const marketingRoutes: RouteRecordRaw = {
  path: '/',
  component: () => import('@/layouts/PlatformLayout.vue'),
  children: [
    { path: '', name: 'landing', component: () => import('./LandingView.vue'), meta: { titleKey: 'pages.landing' } },
    { path: 'pricing', name: 'pricing', component: () => import('./PricingView.vue'), meta: { titleKey: 'pages.pricing' } },
    { path: 'templates', name: 'templates', component: () => import('./TemplatesView.vue'), meta: { titleKey: 'pages.templates' } },
    { path: 'case-study/bca', name: 'case-study', component: () => import('./CaseStudyView.vue'), meta: { titleKey: 'pages.caseStudy' } },
    // Component showcase: development builds only (import.meta.env.DEV is false in production builds, so the route and its chunk are dropped).
    ...(import.meta.env.DEV ? [{ path: 'components', name: 'components', component: () => import('./ComponentsView.vue'), meta: { titleKey: 'pages.components' } }] : []),
    { path: 'login', name: 'login', component: () => import('@/features/platform/LoginView.vue'), meta: { titleKey: 'pages.login' } },
    { path: 'signup', name: 'signup', component: () => import('@/features/platform/SignupView.vue'), meta: { titleKey: 'pages.signup' } },
    { path: 'forgot-password', name: 'forgot-password', component: () => import('@/features/platform/ForgotPasswordView.vue'), meta: { titleKey: 'pages.forgotPassword' } },
    { path: 'reset-password', name: 'reset-password', component: () => import('@/features/platform/ResetPasswordView.vue'), meta: { titleKey: 'pages.resetPassword' } },
    { path: 'privacy', name: 'privacy', component: () => import('./LegalView.vue'), meta: { titleKey: 'pages.privacy' } },
    { path: 'terms', name: 'terms', component: () => import('./LegalView.vue'), meta: { titleKey: 'pages.terms' } },
    { path: 'contact', name: 'contact', component: () => import('./ContactView.vue'), meta: { titleKey: 'pages.contact' } },
  ],
}
