// Tests for index (37 cases), e.g. maintenance gate; redirects the homepage to the under-construction page; redirects an unrelated public page to the under-construction page.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const mockGetSession = vi.fn()
const mockOnAuthStateChange = vi.fn()
const mockFetchSettings = vi.fn()

vi.mock('../../services/supabaseClient', () => ({
  supabase: {
    auth: {
      getSession: (...args: unknown[]) => mockGetSession(...args),
      onAuthStateChange: (...args: unknown[]) => mockOnAuthStateChange(...args),
    },
  },
}))

vi.mock('../../services/settingsApi', () => ({
  fetchSettings: (...args: unknown[]) => mockFetchSettings(...args),
}))

import { router } from '../index'

function mockAuthenticatedAs(role: string) {
  mockGetSession.mockResolvedValue({
    data: { session: { access_token: 'fake-token', user: { user_metadata: {} } } },
  })
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, email: 'test@example.com', phone: null, role }),
    }),
  )
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  vi.unstubAllGlobals()
  mockGetSession.mockResolvedValue({ data: { session: null } })
  mockOnAuthStateChange.mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } })
  // The gate's on/off state is fetched once (memoized) from the backend — the module-level
  // maintenance mode promise in router/index.ts was already resolved to `true` the first time
  // any test in this file navigated, so this mock mainly documents what backs it; see the
  // separate "maintenance gate disabled" suite below for the off case, which needs a fresh
  // module instance to observe a different value.
  mockFetchSettings.mockResolvedValue({
    contact_email: '',
    contact_phone: '',
    contact_address: '',
    maintenance_mode: true,
    maintenance_allowed_event_slugs: 'mahalaya-2026',
  })
})

// Temporary go-live gate (see router/index.ts) — only the one live event + its sub-routes,
// order lookup, check-in, and the admin/member/auth areas stay reachable while the rest of
// the public site isn't ready yet.
describe('maintenance gate', () => {
  it('redirects the homepage to the under-construction page', async () => {
    await router.push('/')
    expect(router.currentRoute.value.path).toBe('/under-construction')
  })

  it('redirects an unrelated public page to the under-construction page', async () => {
    await router.push('/gallery')
    expect(router.currentRoute.value.path).toBe('/under-construction')
  })

  it('redirects a different event slug to the under-construction page', async () => {
    await router.push('/events/some-other-event')
    expect(router.currentRoute.value.path).toBe('/under-construction')
  })

  it('does not redirect the allowed event page', async () => {
    await router.push('/events/mahalaya-2026')
    expect(router.currentRoute.value.path).toBe('/events/mahalaya-2026')
  })

  it('does not redirect the allowed event\'s ticket purchase sub-route', async () => {
    await router.push('/events/mahalaya-2026/tickets')
    expect(router.currentRoute.value.path).toBe('/events/mahalaya-2026/tickets')
  })

  it('does not redirect the guest order lookup page', async () => {
    await router.push('/orders/lookup')
    expect(router.currentRoute.value.path).toBe('/orders/lookup')
  })

  it('does not redirect the terms of sale page', async () => {
    await router.push('/terms-of-sale')
    expect(router.currentRoute.value.path).toBe('/terms-of-sale')
  })

  it('does not redirect the privacy policy page', async () => {
    await router.push('/privacy')
    expect(router.currentRoute.value.path).toBe('/privacy')
  })

  it('does not maintenance-redirect admin/member/checkin/auth routes', async () => {
    await router.push('/admin')
    expect(router.currentRoute.value.path).not.toBe('/under-construction')

    await router.push('/member')
    expect(router.currentRoute.value.path).not.toBe('/under-construction')

    await router.push('/checkin')
    expect(router.currentRoute.value.path).not.toBe('/under-construction')

    await router.push('/login')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('blocks a logged-in non-admin (member) from the member area', async () => {
    mockAuthenticatedAs('member')
    await router.push('/member')
    expect(router.currentRoute.value.path).toBe('/under-construction')
  })

  it('allows a logged-in volunteer into check-in (only admin/member stay admin-only)', async () => {
    mockAuthenticatedAs('volunteer')
    await router.push('/checkin')
    expect(router.currentRoute.value.path).toBe('/checkin')
  })

  it('blocks a logged-in member from check-in (its own route meta restricts to admin/volunteer)', async () => {
    mockAuthenticatedAs('member')
    // Force a real navigation change — the previous test already left the router at
    // /checkin, and re-pushing the same path is a Vue Router no-op that skips guards.
    await router.push('/login')
    await router.push('/checkin')
    expect(router.currentRoute.value.path).not.toBe('/checkin')
  })

  it('allows a logged-in admin into admin/member/checkin', async () => {
    mockAuthenticatedAs('admin')

    await router.push('/admin')
    expect(router.currentRoute.value.path).toBe('/admin')

    await router.push('/member')
    expect(router.currentRoute.value.path).toBe('/member')

    await router.push('/checkin')
    expect(router.currentRoute.value.path).toBe('/checkin')
  })
})

// The gate reads its on/off state from the backend (SiteSettings.maintenance_mode) at
// runtime rather than a hardcoded constant, so an admin can flip it off from /admin/settings
// with no frontend rebuild/redeploy. This suite proves the "off" case actually opens the
// site — it needs a fresh module instance (vi.resetModules + a dynamic re-import) since the
// real router memoizes the fetched value once per app session.
describe('maintenance gate disabled (fetched from the backend)', () => {
  it('does not redirect an otherwise-gated page when maintenance_mode is false', async () => {
    vi.resetModules()
    mockFetchSettings.mockResolvedValue({
      contact_email: '',
      contact_phone: '',
      contact_address: '',
      maintenance_mode: false,
    })

    const { router: freshRouter } = await import('../index')
    await freshRouter.push('/gallery')

    expect(freshRouter.currentRoute.value.path).toBe('/gallery')
  })
})

// The allowed event's slug is admin-configurable (SiteSettings.maintenance_allowed_event_slugs)
// rather than a hardcoded route literal, so this suite proves the gate actually follows a
// differently-configured slug instead of only ever recognizing "mahalaya-2026".
describe('maintenance gate — configurable allowed event slug', () => {
  it('allows whichever event slug is configured in settings, not a hardcoded one', async () => {
    vi.resetModules()
    mockFetchSettings.mockResolvedValue({
      contact_email: '',
      contact_phone: '',
      contact_address: '',
      maintenance_mode: true,
      maintenance_allowed_event_slugs: 'saraswati-2027',
    })

    const { router: freshRouter } = await import('../index')

    await freshRouter.push('/events/saraswati-2027')
    expect(freshRouter.currentRoute.value.path).toBe('/events/saraswati-2027')

    await freshRouter.push('/events/mahalaya-2026')
    expect(freshRouter.currentRoute.value.path).toBe('/under-construction')
  })

  it('allows no event page when no slug is configured', async () => {
    vi.resetModules()
    mockFetchSettings.mockResolvedValue({
      contact_email: '',
      contact_phone: '',
      contact_address: '',
      maintenance_mode: true,
      maintenance_allowed_event_slugs: '',
    })

    const { router: freshRouter } = await import('../index')
    await freshRouter.push('/events/mahalaya-2026')

    expect(freshRouter.currentRoute.value.path).toBe('/under-construction')
  })

  it('allows every event slug in a comma-separated list', async () => {
    vi.resetModules()
    mockFetchSettings.mockResolvedValue({
      contact_email: '',
      contact_phone: '',
      contact_address: '',
      maintenance_mode: true,
      maintenance_allowed_event_slugs: 'mahalaya-2026, saraswati-2027',
    })

    const { router: freshRouter } = await import('../index')

    await freshRouter.push('/events/mahalaya-2026')
    expect(freshRouter.currentRoute.value.path).toBe('/events/mahalaya-2026')

    await freshRouter.push('/events/saraswati-2027/tickets')
    expect(freshRouter.currentRoute.value.path).toBe('/events/saraswati-2027/tickets')

    await freshRouter.push('/events/some-other-event')
    expect(freshRouter.currentRoute.value.path).toBe('/under-construction')
  })
})

// A second, independent allowlist (SiteSettings.maintenance_allowed_page_paths) alongside the
// event-slug one above — lets an admin also open the app's own fixed top-level pages (home,
// heritage, etc.) without touching which event slug(s) stay reachable.
describe('maintenance gate — configurable allowed main pages', () => {
  it('allows only the configured pages, not every fixed top-level page', async () => {
    vi.resetModules()
    mockFetchSettings.mockResolvedValue({
      contact_email: '',
      contact_phone: '',
      contact_address: '',
      maintenance_mode: true,
      maintenance_allowed_event_slugs: '',
      maintenance_allowed_page_paths: 'home',
    })

    const { router: freshRouter } = await import('../index')

    await freshRouter.push('/')
    expect(freshRouter.currentRoute.value.path).toBe('/')

    await freshRouter.push('/about')
    expect(freshRouter.currentRoute.value.path).toBe('/under-construction')
  })

  it('allows every page key in a comma-separated list, including a gallery detail sub-route', async () => {
    vi.resetModules()
    mockFetchSettings.mockResolvedValue({
      contact_email: '',
      contact_phone: '',
      contact_address: '',
      maintenance_mode: true,
      maintenance_allowed_event_slugs: '',
      maintenance_allowed_page_paths: 'heritage, gallery',
    })

    const { router: freshRouter } = await import('../index')

    await freshRouter.push('/about')
    expect(freshRouter.currentRoute.value.path).toBe('/about')

    await freshRouter.push('/gallery/42')
    expect(freshRouter.currentRoute.value.path).toBe('/gallery/42')

    await freshRouter.push('/contact')
    expect(freshRouter.currentRoute.value.path).toBe('/under-construction')
  })

  it('ignores an unrecognized page key rather than crashing the gate', async () => {
    vi.resetModules()
    mockFetchSettings.mockResolvedValue({
      contact_email: '',
      contact_phone: '',
      contact_address: '',
      maintenance_mode: true,
      maintenance_allowed_event_slugs: '',
      maintenance_allowed_page_paths: 'not-a-real-page',
    })

    const { router: freshRouter } = await import('../index')
    await freshRouter.push('/about')

    expect(freshRouter.currentRoute.value.path).toBe('/under-construction')
  })
})

describe('404 catch-all', () => {
  it('resolves an unknown top-level path to the not-found page (maintenance mode off)', async () => {
    vi.resetModules()
    mockFetchSettings.mockResolvedValue({
      contact_email: '',
      contact_phone: '',
      contact_address: '',
      maintenance_mode: false,
    })

    const { router: freshRouter } = await import('../index')
    await freshRouter.push('/this-page-does-not-exist')

    expect(freshRouter.currentRoute.value.name).toBe('not-found')
  })

  it('resolves an unknown sub-path under an allowed maintenance prefix to the not-found page', async () => {
    // Regression check: a path like /admin/typo previously slipped past the maintenance
    // gate (its prefix is allowed) with no matching route, leaving Vue Router unresolved
    // instead of showing a real 404 page.
    mockAuthenticatedAs('admin')
    await router.push('/admin/this-does-not-exist')

    expect(router.currentRoute.value.name).toBe('not-found')
  })
})

// Page visibility "Admin": a page NOT in maintenance_allowed_page_paths is hidden from the
// public, but a signed-in admin may still open it (and sees the "Admin preview" banner state).
describe('maintenance gate — admin preview of Admin-visibility pages', () => {
  async function freshRouterWith(pagePaths: string) {
    vi.resetModules()
    mockFetchSettings.mockResolvedValue({
      contact_email: '',
      contact_phone: '',
      contact_address: '',
      maintenance_mode: true,
      maintenance_allowed_event_slugs: '',
      maintenance_allowed_page_paths: pagePaths,
    })
    const { router: freshRouter } = await import('../index')
    const { useAdminPreview } = await import('../../composables/useAdminPreview')
    return { freshRouter, preview: useAdminPreview().adminPreviewActive }
  }

  it('lets a signed-in admin open a non-published main page and flags the preview', async () => {
    mockAuthenticatedAs('admin')
    const { freshRouter, preview } = await freshRouterWith('home')

    await freshRouter.push('/committee')
    expect(freshRouter.currentRoute.value.path).toBe('/committee')
    expect(preview.value).toBe(true)

    await freshRouter.push('/gallery/42')
    expect(freshRouter.currentRoute.value.path).toBe('/gallery/42')
  })

  it('does not flag a preview on a Published page, even for an admin', async () => {
    mockAuthenticatedAs('admin')
    const { freshRouter, preview } = await freshRouterWith('home')

    await freshRouter.push('/')
    expect(freshRouter.currentRoute.value.path).toBe('/')
    expect(preview.value).toBe(false)
  })

  it('still redirects a signed-in non-admin and an anonymous visitor', async () => {
    mockAuthenticatedAs('member')
    const { freshRouter } = await freshRouterWith('home')
    await freshRouter.push('/committee')
    expect(freshRouter.currentRoute.value.path).toBe('/under-construction')

    mockGetSession.mockResolvedValue({ data: { session: null } })
    const anon = await freshRouterWith('home')
    await anon.freshRouter.push('/committee')
    expect(anon.freshRouter.currentRoute.value.path).toBe('/under-construction')
  })

  it('does not let even an admin into a non-main-page path', async () => {
    mockAuthenticatedAs('admin')
    const { freshRouter } = await freshRouterWith('home')

    await freshRouter.push('/some-unknown-page')
    expect(freshRouter.currentRoute.value.path).toBe('/under-construction')
  })
})

// Page visibility "Visible" toggle off (SiteSettings.maintenance_hidden_page_paths): the page is
// switched off for everyone, admins included, and wins over Published.
describe('maintenance gate — hidden pages', () => {
  async function freshRouterWithHidden(published: string, hidden: string, slugs = '') {
    vi.resetModules()
    mockFetchSettings.mockResolvedValue({
      contact_email: '',
      contact_phone: '',
      contact_address: '',
      maintenance_mode: true,
      maintenance_allowed_event_slugs: slugs,
      maintenance_allowed_page_paths: published,
      maintenance_hidden_page_paths: hidden,
    })
    return (await import('../index')).router
  }

  it('blocks a hidden page (and its sub-routes) even for an admin, and even if also Published', async () => {
    mockAuthenticatedAs('admin')
    const r = await freshRouterWithHidden('committee,gallery', 'committee,gallery')

    await r.push('/committee')
    expect(r.currentRoute.value.path).toBe('/under-construction')
    await r.push('/gallery/42')
    expect(r.currentRoute.value.path).toBe('/under-construction')
  })

  it('hiding the Events list does not hide an allowed event page', async () => {
    const r = await freshRouterWithHidden('', 'events', 'mahalaya-2026')

    await r.push('/events')
    expect(r.currentRoute.value.path).toBe('/under-construction')
    await r.push('/events/mahalaya-2026')
    expect(r.currentRoute.value.path).toBe('/events/mahalaya-2026')
  })

  it('leaves non-hidden pages unaffected for an admin preview', async () => {
    mockAuthenticatedAs('admin')
    const r = await freshRouterWithHidden('', 'committee')

    await r.push('/about')
    expect(r.currentRoute.value.path).toBe('/about')
  })

  it('the old address /heritage still reaches the About page (W11-R44)', async () => {
    mockAuthenticatedAs('admin')
    const r = await freshRouterWithHidden('', 'committee')

    await r.push('/heritage')
    expect(r.currentRoute.value.path).toBe('/about')
  })
})
