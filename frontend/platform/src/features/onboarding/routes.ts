import type { RouteRecordRaw } from 'vue-router'

export const onboardingRoutes: RouteRecordRaw = {
  path: '/start',
  component: () => import('@/layouts/OnboardingLayout.vue'),
  children: [{ path: '', name: 'start', component: () => import('./WizardView.vue'), meta: { titleKey: 'pages.start' } }],
}
