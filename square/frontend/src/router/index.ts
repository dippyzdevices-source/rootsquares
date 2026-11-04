import { moduleEnabled, offeredPhrase, pathAvailable } from '../services/modules'
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    roles?: string[]
    title?: string
    description?: string
  }
}

import { squareProfile } from '../services/squareConfig'
import AdminLayout from '../layouts/AdminLayout.vue'

const squareName = squareProfile.name // the square's own name in page descriptions (W6-R36)
import MemberLayout from '../layouts/MemberLayout.vue'
import PublicLayout from '../layouts/PublicLayout.vue'
import CheckinLayout from '../layouts/CheckinLayout.vue'
import MembershipDriveLayout from '../layouts/MembershipDriveLayout.vue'
import HomeView from '../pages/public/HomeView.vue'
import LayoutHome from '../layout-themes/LayoutHome.vue'
import EngineHome from '../layout-themes/engine/EngineHome.vue'
import JapandiHome from '../layout-themes/japandi/JapandiHome.vue'
import { activeLayout } from '../layout-themes/layouts'
import EventsListView from '../pages/public/EventsListView.vue'
import EventDetailView from '../pages/public/EventDetailView.vue'
import TicketPurchaseView from '../pages/public/TicketPurchaseView.vue'
import OrderLookupView from '../pages/public/OrderLookupView.vue'
import NewsletterSubscribeView from '../pages/public/NewsletterSubscribeView.vue'
import DonateView from '../pages/public/DonateView.vue'
import DonateThanksView from '../pages/public/DonateThanksView.vue'
import AdminDonationsView from '../pages/admin/AdminDonationsView.vue'
import AdminMessagesListView from '../pages/admin/AdminMessagesListView.vue'
import AdminMessageFormView from '../pages/admin/AdminMessageFormView.vue'
import AdminMessageRulesView from '../pages/admin/AdminMessageRulesView.vue'
import MessagesUnsubscribeView from '../pages/public/MessagesUnsubscribeView.vue'
import VippsReturnView from '../pages/public/VippsReturnView.vue'
import AdminOrdersListView from '../pages/admin/AdminOrdersListView.vue'
import AdminTicketsView from '../pages/admin/AdminTicketsView.vue'
import AdminSettingsView from '../pages/admin/AdminSettingsView.vue'
import AdminAuditLogView from '../pages/admin/AdminAuditLogView.vue'
import AdminCheckinView from '../pages/admin/AdminCheckinView.vue'
import AdminMembershipTypesView from '../pages/admin/AdminMembershipTypesView.vue'
import AdminMembersImportView from '../pages/admin/AdminMembersImportView.vue'
import AdminPaymentsView from '../pages/admin/AdminPaymentsView.vue'
import AdminDashboardView from '../pages/admin/AdminDashboardView.vue'
import AdminVolunteersView from '../pages/admin/AdminVolunteersView.vue'
import AdminEventPassView from '../pages/admin/AdminEventPassView.vue'
import AdminMessageBuyersView from '../pages/admin/AdminMessageBuyersView.vue'
import EventOverView from '../pages/public/EventOverView.vue'
import AdminOrderDetailView from '../pages/admin/AdminOrderDetailView.vue'
import HeritageView from '../pages/public/HeritageView.vue'
import CommitteeView from '../pages/public/CommitteeView.vue'
import MembershipView from '../pages/public/MembershipView.vue'
import ContactView from '../pages/public/ContactView.vue'
import TermsOfSaleView from '../pages/public/TermsOfSaleView.vue'
import PrivacyPolicyView from '../pages/public/PrivacyPolicyView.vue'
import TestimonialSubmitView from '../pages/public/TestimonialSubmitView.vue'
import NewsletterUnsubscribeView from '../pages/public/NewsletterUnsubscribeView.vue'
import NewsletterConfirmView from '../pages/public/NewsletterConfirmView.vue'
import AdminNewsletterView from '../pages/admin/AdminNewsletterView.vue'
import AdminNewsletterIssuesView from '../pages/admin/AdminNewsletterIssuesView.vue'
import GalleryView from '../pages/public/GalleryView.vue'
import GalleryAlbumView from '../pages/public/GalleryAlbumView.vue'
import NewsListView from '../pages/public/NewsListView.vue'
import NewsDetailView from '../pages/public/NewsDetailView.vue'
import AdminEventsListView from '../pages/admin/AdminEventsListView.vue'
import AdminEventFormView from '../pages/admin/AdminEventFormView.vue'
import AdminMemberDuplicatesView from '../pages/admin/AdminMemberDuplicatesView.vue'
import AdminMembersFollowUpView from '../pages/admin/AdminMembersFollowUpView.vue'
import AdminUsersLogView from '../pages/admin/AdminUsersLogView.vue'
import AdminMembersListView from '../pages/admin/AdminMembersListView.vue'
import AdminMemberDetailView from '../pages/admin/AdminMemberDetailView.vue'
import AdminGalleryListView from '../pages/admin/AdminGalleryListView.vue'
import AdminGalleryDetailView from '../pages/admin/AdminGalleryDetailView.vue'
import AdminNewsListView from '../pages/admin/AdminNewsListView.vue'
import AdminNewsFormView from '../pages/admin/AdminNewsFormView.vue'
import AdminTestimonialsListView from '../pages/admin/AdminTestimonialsListView.vue'
import AdminTestimonialFormView from '../pages/admin/AdminTestimonialFormView.vue'
import AdminCommitteeListView from '../pages/admin/AdminCommitteeListView.vue'
import AdminCommitteeFormView from '../pages/admin/AdminCommitteeFormView.vue'
import AdminContactDetailsView from '../pages/admin/AdminContactDetailsView.vue'
import AdminLegalTextsView from '../pages/admin/AdminLegalTextsView.vue'
import AdminHomeContentView from '../pages/admin/AdminHomeContentView.vue'
import AdminHeaderFooterView from '../pages/admin/AdminHeaderFooterView.vue'
import AdminPageSettingsView from '../pages/admin/AdminPageSettingsView.vue'
import AdminFoundersListView from '../pages/admin/AdminFoundersListView.vue'
import AdminFoundersFormView from '../pages/admin/AdminFoundersFormView.vue'
import MagazineDetailView from '../pages/public/MagazineDetailView.vue'
import AdminMagazinesListView from '../pages/admin/AdminMagazinesListView.vue'
import AdminMagazinesFormView from '../pages/admin/AdminMagazinesFormView.vue'
import AdminTypographyView from '../pages/admin/AdminTypographyView.vue'
import AdminPaymentsSettingsView from '../pages/admin/AdminPaymentsSettingsView.vue'
import AdminLookupsView from '../pages/admin/AdminLookupsView.vue'
import AdminSponsorsListView from '../pages/admin/AdminSponsorsListView.vue'
import AdminSponsorsFormView from '../pages/admin/AdminSponsorsFormView.vue'
import AdminContentView from '../pages/admin/AdminContentView.vue'
import AdminAccountingEventsView from '../pages/admin/AdminAccountingEventsView.vue'
import AdminAccountingDashboardView from '../pages/admin/AdminAccountingDashboardView.vue'
import AdminAccountingGeneralView from '../pages/admin/AdminAccountingGeneralView.vue'
import MemberDashboardView from '../pages/member/MemberDashboardView.vue'
import MemberFamilyView from '../pages/member/MemberFamilyView.vue'
import MemberTicketsView from '../pages/member/MemberTicketsView.vue'
import MemberVolunteeringView from '../pages/member/MemberVolunteeringView.vue'
import MemberPaymentsView from '../pages/member/MemberPaymentsView.vue'
import MemberSettingsView from '../pages/member/MemberSettingsView.vue'
import CheckinScanView from '../pages/checkin/CheckinScanView.vue'
import MembershipDriveView from '../pages/admin/MembershipDriveView.vue'
import LoginView from '../pages/public/LoginView.vue'
import RegisterView from '../pages/public/RegisterView.vue'
import ForgotPasswordView from '../pages/public/ForgotPasswordView.vue'
import ResetPasswordView from '../pages/public/ResetPasswordView.vue'
import UnderConstructionView from '../pages/public/UnderConstructionView.vue'
import NotFoundView from '../pages/public/NotFoundView.vue'
import { useAuthStore } from '../stores/auth'
import { sendPageView } from '../services/analyticsBeacon'
import { inSupportSession } from '../services/supportSession'
import { demoActive } from '../demo/install'
import { setPageMeta } from '../composables/usePageMeta'
import { loadHomeContent, menuName, type PageKey } from '../services/siteContent'
import { fetchSettings } from '../services/settingsApi'
import { setAdminPreview } from '../composables/useAdminPreview'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: PublicLayout,
    children: [
      {
        path: '',
        name: 'home',
        component: activeLayout ? (squareProfile.themeId === 'japandi-atelier' ? JapandiHome : activeLayout.engine ? EngineHome : LayoutHome) : HomeView, // a layout theme composes its own home page (W9-R5)
        meta: {
          title: '',
          description: offeredPhrase() ? `${squareName} — ${offeredPhrase()}.` : squareName,
        },
      },
      {
        path: 'events',
        name: 'events',
        component: EventsListView,
        meta: { title: 'Events', description: `Upcoming and past ${squareName} events.` },
      },
      {
        path: 'events/:slug',
        name: 'event-detail',
        component: EventDetailView,
        meta: { title: 'Event' },
      },
      {
        path: 'events/:slug/tickets',
        name: 'ticket-purchase',
        component: TicketPurchaseView,
        meta: { title: 'Buy tickets' },
      },
      { path: 'heritage', redirect: '/about' }, // the old address of the About page (W11-R44): bookmarks and links keep working
      {
        path: 'about',
        name: 'heritage',
        component: HeritageView,
        meta: { title: 'About', description: `About ${squareName} — our mission, values, and community.` },
      },
      {
        path: 'committee',
        name: 'committee',
        component: CommitteeView,
        meta: { title: 'Committee', description: `Meet the volunteers who run ${squareName}.` },
      },
      {
        path: 'gallery',
        name: 'gallery',
        component: GalleryView,
        meta: { title: 'Gallery', description: `Photos from ${squareName} events and festivals.` },
      },
      {
        path: 'gallery/:id',
        name: 'gallery-album',
        component: GalleryAlbumView,
        meta: { title: 'Gallery' },
      },
      {
        path: 'membership',
        name: 'membership',
        component: MembershipView,
        meta: {
          title: 'Membership',
          description: `Membership types, benefits, and how to join ${squareName}.`,
        },
      },
      {
        path: 'news',
        name: 'news',
        component: NewsListView,
        meta: { title: 'News', description: `Latest news and announcements from ${squareName}.` },
      },
      {
        path: 'news/magazines/:slug',
        name: 'magazine-detail',
        component: MagazineDetailView,
        meta: { title: 'Magazine' },
      },
      {
        path: 'news/:slug',
        name: 'news-detail',
        component: NewsDetailView,
        meta: { title: 'News' },
      },
      {
        path: 'contact',
        name: 'contact',
        component: ContactView,
        meta: { title: 'Contact', description: `Get in touch with ${squareName}.` },
      },
      {
        path: 'terms-of-sale',
        name: 'terms-of-sale',
        component: TermsOfSaleView,
        meta: { title: 'Terms of Sale', description: `Terms of Sale for event tickets purchased from ${squareName}.` },
      },
      {
        path: 'privacy',
        name: 'privacy',
        component: PrivacyPolicyView,
        meta: { title: 'Privacy Policy', description: `How ${squareName} collects, uses and protects your personal data.` },
      },
      {
        path: 'testimonials',
        name: 'testimonials-submit',
        component: TestimonialSubmitView,
        meta: { title: 'Share your story', description: `Tell us what ${squareName} means to you.` },
      },
      { path: 'messages/unsubscribe', name: 'messages-unsubscribe', component: MessagesUnsubscribeView, meta: { title: 'Unsubscribe' } },
      { path: 'newsletter', name: 'newsletter', component: NewsletterSubscribeView, meta: { title: 'Newsletter' } },
      { path: 'newsletter/confirm', name: 'newsletter-confirm', component: NewsletterConfirmView, meta: { title: 'Confirm your subscription' } },
      {
        path: 'newsletter/unsubscribe',
        name: 'newsletter-unsubscribe',
        component: NewsletterUnsubscribeView,
        meta: { title: 'Unsubscribe from the newsletter' },
      },
      { path: 'login', name: 'login', component: LoginView, meta: { title: 'Log in' } },
      { path: 'register', name: 'register', component: RegisterView, meta: { title: 'Register' } },
      {
        path: 'forgot-password',
        name: 'forgot-password',
        component: ForgotPasswordView,
        meta: { title: 'Reset your password' },
      },
      {
        path: 'reset-password',
        name: 'reset-password',
        component: ResetPasswordView,
        meta: { title: 'Reset your password' },
      },
      {
        path: 'orders/vipps-return',
        name: 'vipps-return',
        component: VippsReturnView,
        meta: { title: 'Checking your payment' },
      },
      { path: 'donate', name: 'donate', component: DonateView, meta: { title: 'Donate' } },
      { path: 'donate/thanks', name: 'donate-thanks', component: DonateThanksView, meta: { title: 'Thank you' } },
      {
        path: 'orders/lookup',
        name: 'order-lookup',
        component: OrderLookupView,
        meta: { title: 'Find your order' },
      },
      {
        path: 'under-construction',
        name: 'under-construction',
        component: UnderConstructionView,
        meta: { title: 'Under construction' },
      },
    ],
  },
  {
    path: '/event-over',
    name: 'event-over',
    component: EventOverView,
    meta: { title: 'The event is over' },
  },
  {
    path: '/admin',
    component: AdminLayout,
    meta: { requiresAuth: true, roles: ['admin'] },
    children: [
      {
        path: '',
        name: 'admin-dashboard',
        component: AdminDashboardView,
        meta: { title: 'Admin Dashboard' },
      },
      {
        path: 'checkin',
        name: 'admin-checkin',
        component: AdminCheckinView,
        meta: { title: 'Admin — Check-in' },
      },
      {
        path: 'events',
        name: 'admin-events',
        component: AdminEventsListView,
        meta: { title: 'Admin — Events' },
      },
      {
        path: 'events/new',
        name: 'admin-events-new',
        component: AdminEventFormView,
        meta: { title: 'Admin — New event' },
      },
      {
        path: 'events/:id/edit',
        name: 'admin-events-edit',
        component: AdminEventFormView,
        meta: { title: 'Admin — Edit event' },
      },
      {
        path: 'members',
        name: 'admin-members',
        component: AdminMembersListView,
        meta: { title: 'Admin — Members' },
      },
      {
        path: 'members/duplicates',
        name: 'admin-member-duplicates',
        component: AdminMemberDuplicatesView,
        meta: { title: 'Admin — Duplicate members' },
      },
      {
        path: 'members/follow-up',
        name: 'admin-members-follow-up',
        component: AdminMembersFollowUpView,
        meta: { title: 'Admin — Awaiting payment' },
      },
      {
        path: 'members/users',
        name: 'admin-members-users',
        component: AdminUsersLogView,
        meta: { title: 'Admin — Users' },
      },
      {
        path: 'members/:id',
        name: 'admin-member-detail',
        component: AdminMemberDetailView,
        meta: { title: 'Admin — Member' },
      },
      {
        path: 'members/import',
        name: 'admin-members-import',
        component: AdminMembersImportView,
        meta: { title: 'Admin — Import members' },
      },
      {
        path: 'memberships',
        name: 'admin-memberships',
        // Merged into the Members list (status filter + Approve); old links keep working.
        redirect: (to) => ({ path: '/admin/members', query: to.query }),
      },
      {
        path: 'membership-types',
        name: 'admin-membership-types',
        component: AdminMembershipTypesView,
        meta: { title: 'Admin — Membership Types' },
      },
      {
        path: 'tickets',
        name: 'admin-tickets',
        component: AdminTicketsView,
        meta: { title: 'Admin — Tickets' },
      },
      {
        path: 'tickets/message',
        name: 'admin-tickets-message',
        component: AdminMessageBuyersView,
        meta: { title: 'Admin — Message ticket buyers' },
      },
      {
        path: 'orders',
        name: 'admin-orders',
        component: AdminOrdersListView,
        meta: { title: 'Admin — Orders' },
      },
      {
        path: 'orders/:id',
        name: 'admin-order-detail',
        component: AdminOrderDetailView,
        meta: { title: 'Admin — Order' },
      },
      { path: 'messages', name: 'admin-messages', component: AdminMessagesListView, meta: { title: 'Admin — Messages' } },
      { path: 'messages/new', name: 'admin-message-new', component: AdminMessageFormView, meta: { title: 'Admin — New message' } },
      { path: 'messages/reminders', name: 'admin-message-reminders', component: AdminMessageRulesView, meta: { title: 'Admin — Reminders' } },
      { path: 'messages/:id', name: 'admin-message', component: AdminMessageFormView, meta: { title: 'Admin — Message' } },
      {
        path: 'donations',
        name: 'admin-donations',
        component: AdminDonationsView,
        meta: { title: 'Admin — Donations' },
      },
      {
        path: 'payments',
        name: 'admin-payments',
        component: AdminPaymentsView,
        meta: { title: 'Admin — Payments' },
      },
      {
        path: 'gallery',
        name: 'admin-gallery',
        component: AdminGalleryListView,
        meta: { title: 'Admin — Gallery' },
      },
      {
        path: 'gallery/new',
        name: 'admin-gallery-new',
        component: AdminGalleryDetailView,
        meta: { title: 'Admin — New album' },
      },
      {
        path: 'gallery/:id',
        name: 'admin-gallery-detail',
        component: AdminGalleryDetailView,
        meta: { title: 'Admin — Album' },
      },
      {
        path: 'news',
        name: 'admin-news',
        component: AdminNewsListView,
        meta: { title: 'Admin — News' },
      },
      {
        path: 'news/new',
        name: 'admin-news-new',
        component: AdminNewsFormView,
        meta: { title: 'Admin — New article' },
      },
      {
        path: 'news/:id/edit',
        name: 'admin-news-edit',
        component: AdminNewsFormView,
        meta: { title: 'Admin — Edit article' },
      },
      {
        path: 'newsletter',
        name: 'admin-newsletter',
        component: AdminNewsletterView,
        meta: { title: 'Admin — Newsletter' },
      },
      {
        path: 'newsletter/issues',
        name: 'admin-newsletter-issues',
        component: AdminNewsletterIssuesView,
        meta: { title: 'Admin — Newsletters' },
      },
      {
        path: 'newsletter/issues/new',
        name: 'admin-newsletter-issue-new',
        redirect: { path: '/admin/messages/new', query: { audience: 'subscribers' } }, // writing moved to Messages (W14-R19)
        meta: { title: 'Admin — New newsletter' },
      },
      {
        path: 'newsletter/issues/:id',
        name: 'admin-newsletter-issue',
        redirect: '/admin/newsletter/issues', // the old editor is gone: a newsletter opens in Messages (W14-R20)
        meta: { title: 'Admin — Newsletter' },
      },
      {
        path: 'testimonials',
        name: 'admin-testimonials',
        component: AdminTestimonialsListView,
        meta: { title: 'Admin — Testimonials' },
      },
      {
        path: 'testimonials/new',
        name: 'admin-testimonials-new',
        component: AdminTestimonialFormView,
        meta: { title: 'Admin — New testimonial' },
      },
      {
        path: 'testimonials/:id/edit',
        name: 'admin-testimonials-edit',
        component: AdminTestimonialFormView,
        meta: { title: 'Admin — Edit testimonial' },
      },
      {
        path: 'content',
        name: 'admin-content',
        component: AdminContentView,
        meta: { title: 'Admin — Settings' },
      },
      {
        path: 'content/settings',
        name: 'admin-content-settings',
        component: AdminSettingsView,
        meta: { title: 'Admin — Site availability' },
      },
      {
        path: 'content/committee',
        name: 'admin-content-committee',
        component: AdminCommitteeListView,
        meta: { title: 'Admin — Committee' },
      },
      {
        path: 'content/committee/new',
        name: 'admin-content-committee-new',
        component: AdminCommitteeFormView,
        meta: { title: 'Admin — New committee member' },
      },
      {
        path: 'content/committee/:id/edit',
        name: 'admin-content-committee-edit',
        component: AdminCommitteeFormView,
        meta: { title: 'Admin — Edit committee member' },
      },
      {
        path: 'content/contact-details',
        name: 'admin-content-contact-details',
        component: AdminContactDetailsView,
        meta: { title: 'Admin — Contact details' },
      },
      {
        path: 'content/pages/:page',
        name: 'admin-content-page',
        component: AdminPageSettingsView,
        props: true,
        meta: { title: 'Admin — Page settings' },
      },
      { path: 'content/page-headings', redirect: { path: '/admin/content', query: { group: 'pages' } } },
      {
        path: 'content/header-footer',
        name: 'admin-content-header-footer',
        component: AdminHeaderFooterView,
        meta: { title: 'Admin — Header & footer' },
      },
      {
        path: 'content/home',
        name: 'admin-content-home',
        component: AdminHomeContentView,
        meta: { title: 'Admin — Home page' },
      },
      {
        path: 'content/legal-texts',
        name: 'admin-content-legal-texts',
        component: AdminLegalTextsView,
        meta: { title: 'Admin — Legal texts' },
      },
      {
        path: 'content/heritage-image',
        redirect: '/admin/content/pages/about',
      },
      {
        path: 'content/founders',
        name: 'admin-content-founders',
        component: AdminFoundersListView,
        meta: { title: 'Admin — Founders' },
      },
      {
        path: 'content/founders/new',
        name: 'admin-content-founders-new',
        component: AdminFoundersFormView,
        meta: { title: 'Admin — New founder' },
      },
      {
        path: 'content/founders/:id/edit',
        name: 'admin-content-founders-edit',
        component: AdminFoundersFormView,
        meta: { title: 'Admin — Edit founder' },
      },
      {
        path: 'content/payments',
        name: 'admin-content-payments',
        component: AdminPaymentsSettingsView,
        meta: { title: 'Admin — Payment settings' },
      },
      {
        path: 'content/typography',
        name: 'admin-content-typography',
        component: AdminTypographyView,
        meta: { title: 'Admin — Typography' },
      },
      {
        path: 'content/lists',
        name: 'admin-content-lists',
        component: AdminLookupsView,
        meta: { title: 'Admin — Lists' },
      },
      {
        path: 'content/sponsors',
        name: 'admin-content-sponsors',
        component: AdminSponsorsListView,
        meta: { title: 'Admin — Sponsors' },
      },
      {
        path: 'content/sponsors/new',
        name: 'admin-content-sponsors-new',
        component: AdminSponsorsFormView,
        meta: { title: 'Admin — New sponsor' },
      },
      {
        path: 'content/sponsors/:id/edit',
        name: 'admin-content-sponsors-edit',
        component: AdminSponsorsFormView,
        meta: { title: 'Admin — Edit sponsor' },
      },
      {
        path: 'news/magazines',
        name: 'admin-news-magazines',
        component: AdminMagazinesListView,
        meta: { title: 'Admin — Magazines' },
      },
      {
        path: 'news/magazines/new',
        name: 'admin-news-magazines-new',
        component: AdminMagazinesFormView,
        meta: { title: 'Admin — New magazine' },
      },
      {
        path: 'news/magazines/:id/edit',
        name: 'admin-news-magazines-edit',
        component: AdminMagazinesFormView,
        meta: { title: 'Admin — Edit magazine' },
      },
      // Magazines moved from Settings into the News area.
      { path: 'content/magazines', redirect: { name: 'admin-news-magazines' } },
      { path: 'content/magazines/new', redirect: { name: 'admin-news-magazines-new' } },
      { path: 'content/magazines/:id/edit', redirect: (to) => `/admin/news/magazines/${to.params.id}/edit` },
      // Legacy top-level paths, kept as redirects so old bookmarks/links still work now that
      // Settings and Committee live under Content.
      { path: 'settings', redirect: { name: 'admin-content-settings' } },
      { path: 'committee', redirect: { name: 'admin-content-committee' } },
      { path: 'committee/new', redirect: { name: 'admin-content-committee-new' } },
      {
        path: 'committee/:id/edit',
        redirect: (to) => ({ name: 'admin-content-committee-edit', params: to.params }),
      },
      {
        path: 'accounting',
        name: 'admin-accounting',
        // Without the Events module the general book is the whole of Accounting (W14-R15)
        component: moduleEnabled('events') ? AdminAccountingEventsView : AdminAccountingGeneralView,
        meta: { title: 'Admin — Accounting' },
      },
      { path: 'accounting/general', name: 'admin-accounting-general', component: AdminAccountingGeneralView, meta: { title: 'Admin — General accounts' } },
      {
        path: 'accounting/:eventId',
        name: 'admin-accounting-dashboard',
        component: AdminAccountingDashboardView,
        meta: { title: 'Admin — Accounting' },
        beforeEnter: () => (moduleEnabled('events') ? true : { name: 'admin-accounting' }),
      },
      {
        path: 'event-pass',
        name: 'admin-event-pass',
        component: AdminEventPassView,
        meta: { title: 'Admin — Event wrap-up' },
      },
      {
        path: 'volunteers',
        name: 'admin-volunteers',
        component: AdminVolunteersView,
        meta: { title: 'Admin — Volunteers' },
      },
      {
        path: 'reports',
        redirect: '/admin',
      },
      {
        path: 'audit-log',
        name: 'admin-audit-log',
        component: AdminAuditLogView,
        meta: { title: 'Admin — Audit Log' },
      },
    ],
  },
  {
    path: '/member',
    component: MemberLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'member-dashboard',
        component: MemberDashboardView,
        meta: { title: 'My Dashboard' },
      },
      {
        // My Membership now lives on the Dashboard (Membership Status section) — redirect
        // rather than leave old links/bookmarks pointing at a dead placeholder.
        path: 'membership',
        redirect: { name: 'member-dashboard' },
      },
      {
        path: 'family',
        name: 'member-family',
        component: MemberFamilyView,
        meta: { title: 'My Family' },
      },
      {
        path: 'tickets',
        name: 'member-tickets',
        component: MemberTicketsView,
        meta: { title: 'My Tickets' },
      },
      {
        path: 'volunteering',
        name: 'member-volunteering',
        component: MemberVolunteeringView,
        meta: { title: 'My Volunteering' },
      },
      {
        path: 'payments',
        name: 'member-payments',
        component: MemberPaymentsView,
        meta: { title: 'Payment History' },
      },
      {
        path: 'settings',
        name: 'member-settings',
        component: MemberSettingsView,
        meta: { title: 'Settings' },
      },
      {
        // Profile editing now lives on Settings (was the Dashboard, before the Portal
        // redesign split Overview/Family/Settings into separate pages).
        path: 'profile',
        redirect: { name: 'member-settings' },
      },
    ],
  },
  {
    path: '/checkin',
    component: CheckinLayout,
    meta: { requiresAuth: true, roles: ['admin', 'volunteer'] },
    children: [
      {
        path: '',
        name: 'checkin-scan',
        component: CheckinScanView,
        meta: { title: 'Scan tickets' },
      },
    ],
  },
  {
    path: '/membership-drive',
    component: MembershipDriveLayout,
    meta: { requiresAuth: true, roles: ['admin', 'volunteer'] },
    children: [
      {
        path: '',
        name: 'membership-drive',
        component: MembershipDriveView,
        meta: { title: 'Membership Drive' },
      },
    ],
  },
  // Development only (W10-R6): every theme side by side. Not in a production build.
  ...(import.meta.env.DEV ? [{ path: '/theme-review', name: 'theme-review', component: () => import('../pages/dev/ThemeReviewView.vue'), meta: { title: 'Theme review' } }] : []),
  // Catch-all — must stay last so it never shadows a real route above it.
  {
    path: '/:pathMatch(.*)*',
    component: PublicLayout,
    children: [
      {
        path: '',
        name: 'not-found',
        component: NotFoundView,
        meta: { title: 'Page not found' },
      },
    ],
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

// --- Temporary go-live gate -------------------------------------------------------------
// The rest of the public site isn't ready yet — only the one live event (and its own
// ticket-purchase sub-route), guest order lookup, check-in/admin/member/auth areas, and the
// legal Terms of Sale and Privacy Policy pages (Terms added 2026-09-28, Privacy 2026-09-29 — a purchaser must be able to read it even while
// the rest of the site is gated, same reasoning as /login/etc. staying reachable) stay
// reachable. Everything else redirects to a friendly "under construction" page
// instead of showing unfinished content. On top of that, `/admin` and `/member` are further
// restricted to the `admin` role only during this window — a plain member or volunteer may
// not in, since the association isn't ready to run those flows for the wider membership yet.
// `/checkin` is deliberately exempt from that admin-only narrowing (see
// MAINTENANCE_ADMIN_ONLY_PATHS below) — a volunteer must still be able to scan tickets at the
// door even while the rest of the site is gated; its own route meta (`roles: ['admin',
// 'volunteer']`) already keeps a plain member out, so nothing extra is needed for that.
//
// Whether the gate is on is read from the backend (`SiteSettings.maintenance_mode`, via the
// public GET /api/settings endpoint) rather than hardcoded here — a Vite env var would be
// baked into the built JS bundle at build time, so flipping it would still need a full
// frontend rebuild + redeploy. Reading it from the backend instead means an admin can toggle
// it from /admin/settings and it takes effect for every visitor immediately, no redeploy of
// either frontend or backend needed. To reopen the full site later: turn the toggle off
// there (or delete this block for good once the rest of the site is ready).
//
// The live event(s)' path used to be a hardcoded '/events/mahalaya-2026' string literal
// here — a self-audit flagged that as a silent-breakage risk (re-slugging that event before
// the gate comes off would strand every visitor on /under-construction with no error signal).
// It's now `SiteSettings.maintenance_allowed_event_slugs` — a comma-separated list, so more
// than one event can stay reachable at once (e.g. during a handover between two festivals) —
// editable from the same /admin/settings "Site availability" card as the on/off toggle, for
// the same no-redeploy reason as maintenance_mode itself.
const MAINTENANCE_ALLOWED_PATHS = [
  '/orders/lookup',
  '/orders/vipps-return',
  '/donate/thanks',
  '/messages/unsubscribe',
  '/checkin',
  '/membership-drive',
  '/admin',
  '/member',
  '/login',
  '/register',
  '/forgot-password',
  '/reset-password',
  '/under-construction',
  '/terms-of-sale',
  '/privacy',
]
// The subset of the above that requires the `admin` role specifically, once authenticated
// (an unauthenticated visit still falls through to the existing requiresAuth -> /login
// redirect below, so an admin can still reach /login to sign in in the first place).
// `/checkin` is intentionally NOT included — a volunteer needs to reach it too, and its own
// route meta already restricts it to admin/volunteer (blocking a plain member) further down.
const MAINTENANCE_ADMIN_ONLY_PATHS = ['/admin', '/member']

// A second, independent allowlist (added 2026-09-28) alongside maintenance_allowed_event_slugs
// above — an admin can additionally open any of the app's own fixed top-level public pages
// while the rest of the site stays gated. Keys, not raw paths, so the backend can validate
// against a known set (app/settings/admin_routes.py's MAINTENANCE_PAGE_KEYS — keep both in
// sync). Events/gallery/news map to their listing page only; their own detail sub-routes come
// along for free via matchesPathOrPrefix below, the same way an allowed event slug already
// covers that event's own /tickets sub-route.
const MAINTENANCE_PAGE_KEY_PATHS: Record<string, string> = {
  home: '/',
  events: '/events',
  heritage: '/about',
  committee: '/committee',
  gallery: '/gallery',
  membership: '/membership',
  news: '/news',
  contact: '/contact',
  testimonials: '/testimonials',
}

function matchesPathOrPrefix(path: string, candidates: string[]): boolean {
  return candidates.some((candidate) => path === candidate || path.startsWith(`${candidate}/`))
}

function isMaintenanceAllowed(path: string, allowedDynamicPaths: string[]): boolean {
  const candidates = [...MAINTENANCE_ALLOWED_PATHS, ...allowedDynamicPaths]
  return matchesPathOrPrefix(path, candidates)
}

// Any of the main pages above (and their detail sub-routes) — an admin may open these even when
// their Page visibility is "Admin", so they can review a page before publishing it.
// A hidden page also hides its detail sub-routes (/gallery/42) — except Events, whose sub-routes
// belong to individual events (allowed slugs / their own Draft flag), not to the listing page.
function isMaintenanceHidden(path: string, hiddenPaths: string[]): boolean {
  return hiddenPaths.some(
    (hidden) => path === hidden || (hidden !== '/events' && hidden !== '/' && path.startsWith(`${hidden}/`)),
  )
}

function isMaintenanceAdminPreviewable(path: string): boolean {
  return matchesPathOrPrefix(path, Object.values(MAINTENANCE_PAGE_KEY_PATHS))
}

function isMaintenanceAdminOnly(path: string): boolean {
  return matchesPathOrPrefix(path, MAINTENANCE_ADMIN_ONLY_PATHS)
}

interface MaintenanceGateState {
  maintenanceMode: boolean
  allowedDynamicPaths: string[]
  /** Page paths switched OFF for everyone, admins included (Visible toggle off). */
  hiddenPaths: string[]
}

// Comma-separated page keys -> their paths, dropping unrecognized keys (stale data from before
// a page was removed) rather than crashing the gate.
function pageKeysToPaths(value: string | undefined): string[] {
  return (value ?? '')
    .split(',')
    .map((key) => key.trim())
    .filter(Boolean)
    .map((key) => MAINTENANCE_PAGE_KEY_PATHS[key])
    .filter((path): path is string => !!path)
}

// Fetched once per app session (memoized, same pattern as authStore.initialize() just below)
// rather than on every navigation — an admin flipping either setting takes effect on the next
// fresh page load/hard refresh, not instantly inside an already-open tab. If the fetch ever
// fails, default to the gate staying on with nothing extra allowlisted — a transient backend
// hiccup should never accidentally expose unfinished pages to the public.
let maintenanceGatePromise: Promise<MaintenanceGateState> | null = null

// Site-wide description typeface (Admin -> Settings). Applied before the first page renders, since the
// gate above awaits this same fetch, so there is no flash of the default font. design-system.css
// keys its --ds-desc-* variables off <html data-desc-style>; unknown/missing falls back to Karla.
function applyDescriptionStyle(style: string | undefined) {
  document.documentElement.dataset.descStyle = style === 'cormorant' || style === 'source' ? style : 'karla'
}

function getMaintenanceGateState(): Promise<MaintenanceGateState> {
  if (!maintenanceGatePromise) {
    maintenanceGatePromise = fetchSettings()
      .then((settings) => {
        applyDescriptionStyle(settings.description_style)
        // Comma-separated in SiteSettings.maintenance_allowed_event_slugs (same convention as
        // Config.FRONTEND_ORIGIN on the backend) — split into one /events/<slug> path per entry.
        const allowedEventPaths = settings.maintenance_allowed_event_slugs
          ? settings.maintenance_allowed_event_slugs
              .split(",")
              .map((slug) => slug.trim())
              .filter(Boolean)
              .map((slug) => `/events/${slug}`)
          : []
        // Published pages (everyone) minus hidden ones — a page in both lists is hidden.
        const hiddenPaths = pageKeysToPaths(settings.maintenance_hidden_page_paths)
        const allowedPagePaths = pageKeysToPaths(settings.maintenance_allowed_page_paths).filter(
          (path) => !hiddenPaths.includes(path),
        )
        return {
          maintenanceMode: settings.maintenance_mode,
          allowedDynamicPaths: [...allowedEventPaths, ...allowedPagePaths],
          hiddenPaths,
        }
      })
      .catch(() => ({ maintenanceMode: true, allowedDynamicPaths: [], hiddenPaths: [] }))
  }
  return maintenanceGatePromise
}

// The addresses that still work while an Event pass is in its archive: the page itself, sign-in and its helpers, the owner's admin area.
const ARCHIVE_PATHS = ['/event-over', '/login', '/forgot-password', '/reset-password', '/auth', '/admin']

// A sleeping square (Keep, W10-R41, W10-R44) is a true sleep: its project may be paused, so there is no sign-in, no admin and no data. App.vue shows the one
// back-soon page (SleepingView) in place of every page, at the address the visitor typed (W17-R24): the router does not redirect, and does nothing else either:
// no maintenance lookup and no sign-in check, because each of those would reach the sleeping square's project and start it again.
router.beforeEach(async (to) => {
  if (squareProfile.sleeping) return true
  // An Event pass in its archive (W11, ADR 044): the event is over. The public site is one page; only sign-in and the owner's admin area stay reachable.
  if (squareProfile.eventPass?.phase === 'archive' && !ARCHIVE_PATHS.some((p) => to.path === p || to.path.startsWith(`${p}/`))) return { path: '/event-over', replace: true }
  // A page of a module the owner turned off does not exist in this square (W8-R9): show the not-found page.
  if (!pathAvailable(to.path)) {
    if (to.path === '/') {
      const first = ['/about', '/events', '/news', '/gallery', '/membership', '/contact', '/login'].find((p) => pathAvailable(p))
      if (first) return { path: first, replace: true } // Home is off in a custom package (W19-R24)
    }
    return { path: '/page-not-available', replace: true }
  }

  const { maintenanceMode, allowedDynamicPaths, hiddenPaths } = await getMaintenanceGateState()

  const authStore = useAuthStore()
  setAdminPreview(false)

  // Switched OFF entirely (Visible toggle off): blocked for everyone, admins included.
  if (maintenanceMode && isMaintenanceHidden(to.path, hiddenPaths)) {
    return { path: '/under-construction', replace: true }
  }

  if (maintenanceMode && !isMaintenanceAllowed(to.path, allowedDynamicPaths)) {
    // A page whose visibility is "Admin": a signed-in admin may still open it (with the
    // "Admin preview" banner), everyone else goes to the under-construction page. Auth is only
    // awaited here, so ordinary visitors of allowed pages never wait on it.
    await authStore.initialize().catch(() => {})
    const isAdmin = authStore.isAuthenticated && authStore.user?.role === 'admin'
    if (isAdmin && isMaintenanceAdminPreviewable(to.path)) {
      setAdminPreview(true)
    } else {
      return { path: '/under-construction', replace: true }
    }
  }

  // Vue Router's initial navigation can start resolving before the app has finished
  // mounting — awaiting here (memoized, so this is a no-op after the first navigation)
  // guarantees auth state is real before any requiresAuth/roles check runs, fixing a
  // race where a hard reload of a protected route could redirect to /login even with a
  // valid session.
  await authStore.initialize().catch(() => {})

  if (
    maintenanceMode &&
    isMaintenanceAdminOnly(to.path) &&
    authStore.isAuthenticated &&
    authStore.user?.role !== 'admin'
  ) {
    return { path: '/under-construction', replace: true }
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return '/login'
  }
  if (to.meta.roles && !(to.meta.roles as string[]).includes(authStore.user?.role ?? '')) {
    return '/'
  }
  return true
})

// The public pages a square can rename (W11-R43): the tab title uses the new name too, once the square's words have arrived.
const RENAMEABLE_PAGES: Record<string, PageKey> = { '/events': 'events', '/about': 'heritage', '/gallery': 'gallery', '/membership': 'membership', '/news': 'news', '/contact': 'contact', '/committee': 'committee' }

router.afterEach((to, from) => {
  if (squareProfile.sleeping) return // the back-soon title and robots tag are set by App.vue
  // the visit counter (ADR 090): a page was shown. Nothing is sent unless the owner switched counting on; never in the admin, for an admin, in a support session or the demo.
  sendPageView(to.path, from.matched.length ? from.path : '', { enabled: squareProfile.analytics, isAdmin: useAuthStore().isAdmin, inSupportSession: inSupportSession(), demo: demoActive() })
  const renamable = RENAMEABLE_PAGES[to.path]
  setPageMeta(renamable ? menuName(renamable, to.meta.title ?? '') : (to.meta.title ?? ''), to.meta.description)
  if (renamable) {
    void loadHomeContent().then(() => {
      if (router.currentRoute.value.path === to.path) setPageMeta(menuName(renamable, to.meta.title ?? ''), to.meta.description)
    })
  }
  // #app (not window) is the real scrolling container (see style.css — html/body are
  // locked to fix iOS Safari's rubber-band bounce), so Vue Router's own built-in
  // scrollBehavior option (which only acts on window.scrollTo) would be a no-op here.
  // Every navigation resets to the top; back/forward no longer restores its old scroll
  // position, a deliberate trade-off for reliably killing the bounce on every platform.
  document.getElementById('app')?.scrollTo({ top: 0 })
})
