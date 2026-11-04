import type { RouteRecordRaw } from 'vue-router'

const page = (path: string, name: string, key: string, component: () => Promise<unknown>): RouteRecordRaw => ({
  path,
  name: `site-${name}`,
  component,
  meta: { titleKey: `site.${key}` },
})

export const tenantSiteRoutes: RouteRecordRaw = {
  path: '/site/:themeId',
  component: () => import('@/layouts/TenantSiteLayout.vue'),
  children: [
    page('', 'home', 'home', () => import('./HomeView.vue')),
    page('events', 'events', 'events', () => import('./EventsView.vue')),
    page('events/:eventId', 'event', 'event', () => import('./EventDetailView.vue')),
    page('events/:eventId/pay', 'pay', 'event', () => import('./PayView.vue')),
    page('order/:orderId', 'order', 'event', () => import('./OrderView.vue')),
    page('news', 'news', 'articles', () => import('./ArticlesView.vue')),
    page('news/:articleId', 'article', 'articles', () => import('./ArticleView.vue')),
    page('membership', 'membership', 'membership', () => import('./MembershipView.vue')),
    page('committee', 'committee', 'committee', () => import('./CommitteeView.vue')),
    page('gallery', 'gallery', 'gallery', () => import('./GalleryView.vue')),
    page('contact', 'contact', 'contact', () => import('./ContactView.vue')),
    page(':pathMatch(.*)*', 'not-found', 'notFound', () => import('./NotFoundView.vue')),
  ],
}
