// Tests for layouts.mount (6 cases), e.g. renders its shell, hero and every section with all modules on; Gallery off: no link, no section, no photo strip; the rest reflows; minimal (no optional module): only Home, Heritage and Contact, buttons.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
// Mounting a whole theme is slow when the full suite runs in parallel (it timed out at 5 s once, W15-R3).
vi.setConfig({ testTimeout: 60000 })  // the first theme mount is slow when the whole suite runs in parallel

// Every layout theme, mounted with a fixture square: the shell and the home page render without a Vue warning, show the headline, and follow the
// module rules of the design (W9-R5): Gallery off, minimal (no optional module), and the compact header under 860 px.
const IDS = ['terracotta-hall',  'hush-pond',  'fjord-grid',  'pencil-notebook',  'linen-arch',  'berry-panel',  'ledger-gazette',  'marquee-showbill',  'canopy-leaf',  'clay-press',  'dune-teal',  'pearl-emboss',  'product-console',  'daylight-agenda',  'torn-kraft',  'sage-round']
const ENGINE_IDS = ['harvest-hall',  'stillwater',  'fjord-modern',  'pencil-club',  'olive-linen',  'berry-courtyard',  'atrium',  'ledger',  'marquee',  'canopy-grove',  'softform',  'daylight',  'sage-cafe',  'japandi-atelier',  'clay-pastel',  'sand-teal',  'pearl',  'product',  'torn-paper',  'verdeo',  'tidewater',  'mela-noir',  'lotus-hour',  'fuchsia-pop',  'kash-meadow',  'cacao-mint',  'garnet-pearl',  'denim-linen',  'orchid-dusk',  'neon-cyan',  'lime-fizz',  'olive-press',  'peach-charcoal',  'citrus-night',  'bone-forest',  'ruby-pop',  'mint-night',  'pewter',  'cobalt-pop']
const ALL = ['events', 'gallery', 'news', 'memberships']

let width = 1280
const iso = (d: number) => `2026-11-${String(d).padStart(2, '0')}T18:00:00`
const event = (i: number) => ({ id: i, title: `Event ${i}`, slug: `event-${i}`, short_description: null, description_style: null, event_type: 'festival', start_datetime: iso(10 + i), end_datetime: null, venue: `Venue ${i}`, banner_image: null, published: true })
const photo = (i: number) => ({ id: i, filename: `p${i}.jpg`, url: `/p${i}.jpg`, thumbnail_url: `/t${i}.jpg`, width: 800, height: 600, caption: `Photo ${i}`, album_id: 1, album_title: 'Album' })
const article = (i: number) => ({ id: i, title: `Story ${i}`, slug: `story-${i}`, summary: 'Summary', description_style: null, banner_image: null, category: null, author: null, read_minutes: 2, published_at: iso(i) })
const HOME = {
  eyebrow: 'Community', headline: 'Bengal kept alive in Oslo', intro: 'A lead paragraph.', local_line: 'স্থানীয়', tagline_local: 'স্থানীয়', utility_text: 'Oslo',
  stats: [{ value: '16', label: 'years' }, { value: '400', label: 'members' }, { value: '12', label: 'events' }], blurb: 'We are volunteers.', footer_copyright: '', footer_blurb: '', footer_registration: '',
  social_links: [], page_headings: {}, about_page: { timeline: [{ year: '2010', title: 'Founded', description: 'A dozen friends.' }, { year: '2019', title: 'Youth section', description: '' }] },
}

async function mountSquare(themeId: string, modules: string[]) {
  vi.resetModules()
  vi.doMock('../services/squareConfig', () => ({ squareProfile: { name: 'Test Square', slug: 't', themeId, currency: 'NOK', logoUrl: '', logoDarkUrl: '', modules }, squareAuth: null }))
  vi.doMock('../services/eventsApi', () => ({ fetchEvents: async () => ({ items: [event(1), event(2), event(3)] }) }))
  vi.doMock('../services/galleryApi', () => ({ fetchGalleryMedia: async () => [1, 2, 3, 4, 5, 6].map(photo), fetchAlbums: async () => ({ items: [] }) }))
  vi.doMock('../services/newsApi', () => ({ fetchNews: async () => ({ items: [article(1), article(2), article(3)] }) }))
  vi.doMock('../services/memberApi', () => ({ fetchMembershipTypes: async () => [{ name: 'Student', price: 100, billing_frequency: 'yearly', contact_for_price: false, description: 'Full access.' }, { name: 'Family', price: 500, billing_frequency: 'yearly', contact_for_price: false }] }))
  vi.doMock('../services/testimonialsApi', () => ({ fetchTestimonials: async () => ({ items: [] }) }))
  vi.doMock('../services/settingsApi', () => ({ fetchSettings: async () => ({ contact_email: 'hello@club.example', contact_phone: '', contact_address: '', about_text: 'The story.\n\nMore story.', heritage_image_url: null }) }))
  vi.doMock('../services/siteContent', async () => {
    const actual = await vi.importActual<typeof import('../services/siteContent')>('../services/siteContent')
    return { ...actual, loadHomeContent: async () => ({ ...actual.EMPTY_HOME_CONTENT, ...HOME }) }
  })
  vi.doMock('../stores/auth', () => ({ useAuthStore: () => ({ isAuthenticated: false, isAdmin: false, signOut: async () => {} }) }))
  vi.doMock('../components/SponsorsMarquee.vue', () => ({ default: { template: '<div />' } }))
  const { default: LayoutShell } = await import('./LayoutShell.vue')
  const { default: LayoutHome } = await import('./LayoutHome.vue')
  const { default: EngineHome } = await import('./engine/EngineHome.vue')
  const { activeLayout } = await import('./layouts')
  const stub = { template: '<p>page</p>' }
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: activeLayout?.engine ? EngineHome : LayoutHome }, ...['events', 'heritage', 'gallery', 'membership', 'news', 'contact', 'login'].map((p) => ({ path: `/${p}`, component: stub }))] })
  await router.push('/')
  await router.isReady()
  const wrapper = mount(LayoutShell, { global: { plugins: [router] } })
  // the shell and the hero load as separate chunks: wait until both are on the page, then let the data arrive
  await vi.waitFor(() => expect(wrapper.find('h1').exists()).toBe(true), { timeout: 8000 })
  for (let i = 0; i < 6; i++) await flushPromises()
  return wrapper
}

let warn: { mock: { calls: unknown[][] }; mockRestore: () => void }
beforeEach(() => {
  width = 1280
  Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, get: () => width })
  warn = vi.spyOn(console, 'warn').mockImplementation(() => {}) as unknown as typeof warn
})
afterEach(() => {
  warn.mockRestore()
  vi.doUnmock('../services/squareConfig')
})
const vueWarnings = () => warn.mock.calls.filter((c) => String(c[0]).includes('[Vue warn]')).map((c) => String(c[0]))
// Stillwater keeps its pages in a full-screen menu: open it first
const openMenu = async (w: ReturnType<typeof mount>) => { const b = w.find('.lt-still-btn'); if (b.exists() && !w.find('.lt-still-overlay').exists()) await b.trigger('click') }
const navLabels = (w: ReturnType<typeof mount>) => w.findAll('nav[aria-label="Main"] a').map((a) => a.text().replace(/^\d+/, '').trim())

describe.each(IDS)('%s', (id) => {
  it('renders its shell, hero and every section with all modules on', async () => {
    const w = await mountSquare(id, ALL)
    expect(vueWarnings()).toEqual([])
    expect(w.find('h1').text()).toContain('Bengal')
    await openMenu(w)
    expect(navLabels(w)).toEqual(['Home', 'Events', 'About', 'Gallery', 'Membership', 'News', 'Contact'])
    for (const key of ['events', 'heritage', 'gallery', 'news', 'membership']) expect(w.find(`.lt-sec-${key}`).exists(), key).toBe(true)
    expect(w.text()).toContain('Event 1')
    expect(w.text()).toContain('Become a member')
    expect(w.find('footer').exists()).toBe(true)
  })

  it('Gallery off: no link, no section, no photo strip; the rest reflows', async () => {
    const w = await mountSquare(id, ['events', 'news', 'memberships'])
    expect(vueWarnings()).toEqual([])
    await openMenu(w)
    expect(navLabels(w)).not.toContain('Gallery')
    expect(w.find('.lt-sec-gallery').exists()).toBe(false)
    expect(w.find('img[src^="/t"]').exists()).toBe(false)
    expect(w.find('.lt-sec-events').exists()).toBe(true)
  })

  it('minimal (no optional module): only Home, Heritage and Contact, buttons lead to Contact and Heritage', async () => {
    const w = await mountSquare(id, [])
    expect(vueWarnings()).toEqual([])
    await openMenu(w)
    expect(navLabels(w)).toEqual(['Home', 'About', 'Contact'])
    for (const key of ['events', 'gallery', 'news', 'membership']) expect(w.find(`.lt-sec-${key}`).exists(), key).toBe(false)
    expect(w.text()).toContain('Get in touch')
    expect(w.text()).not.toContain('Become a member')
    expect(w.find('h1').text()).toContain('Bengal')
  })

  it('under 860 px every theme uses the compact header with a Menu button', async () => {
    width = 390
    const w = await mountSquare(id, ALL)
    expect(vueWarnings()).toEqual([])
    expect(w.find('.lt-compact').exists()).toBe(true)
    const menu = w.find('.lt-c-menu')
    expect(menu.exists()).toBe(true)
    await menu.trigger('click')
    expect(navLabels(w)).toContain('Events')
  })
})

// The engine themes (W9-R10): 39 themes, each from a shell and a layout kit; the home page, the navigation and the module rules.
describe.each(ENGINE_IDS)('%s (engine)', (id) => {
  it('renders its shell and home page with all modules on', async () => {
    const w = await mountSquare(id, ALL)
    expect(vueWarnings()).toEqual([])
    expect(w.find('h1').text()).toContain('Bengal')
    expect(navLabels(w)).toEqual(['Events', 'About', 'Gallery', 'Membership', 'News', 'Contact'])
    expect(w.text()).toContain('Event 1')
    expect(w.find('footer').exists()).toBe(true)
  })

  it('minimal (no optional module): Heritage and Contact only, buttons lead to Contact', async () => {
    const w = await mountSquare(id, [])
    expect(vueWarnings()).toEqual([])
    expect(navLabels(w)).toEqual(['About', 'Contact'])
    expect(w.text()).toContain('Get in touch')
    expect(w.text()).not.toContain('Become a member')
  })
})
