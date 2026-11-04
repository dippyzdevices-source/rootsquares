// Tests for AdminPageSettingsView (9 cases), e.g. AdminPageSettingsView (W6-R75, W8-R4); shows the heading block of one page with what is saved, and only the c; says so for a page that does not exist.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAdminSettings = vi.fn()
const mockUpdateAdminSettings = vi.fn()
vi.mock('../../../services/adminSettingsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminSettingsApi')>('../../../services/adminSettingsApi')
  return { ...actual, fetchAdminSettings: (...a: unknown[]) => mockFetchAdminSettings(...a), updateAdminSettings: (...a: unknown[]) => mockUpdateAdminSettings(...a) }
})
vi.mock('../../../composables/useToast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn() }) }))

import AdminPageSettingsView from '../AdminPageSettingsView.vue'

const stubs = { SettingsSectionNav: true, HeritageMediaCards: true }
const mountPage = (page: string) => mount(AdminPageSettingsView, { props: { page }, global: { stubs } })

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAdminSettings.mockResolvedValue({ home_content: { headline: 'Hello', page_headings: { events: { title: 'What is on' } } } })
  mockUpdateAdminSettings.mockImplementation(async (p: { home_content: object }) => ({ home_content: p.home_content }))
})

describe('AdminPageSettingsView (W6-R75, W8-R4)', () => {
  it('shows the heading block of one page with what is saved, and only the cards of that page', async () => {
    const wrapper = mountPage('events')
    await flushPromises()
    expect(wrapper.findAll('h3').map((h) => h.text())).toEqual(['Heading'])
    expect((wrapper.get('input[aria-label="Events: Title"]').element as HTMLInputElement).value).toBe('What is on')
    expect(wrapper.findAll('input,textarea')).toHaveLength(6)
    const cards = { gallery: ['Heading', 'Gallery: band at the bottom'], news: ['Heading', 'News: newsletter band'], contact: ['Heading', 'Contact: questions and footnote'], about: ['Heading', 'About: sections', 'Photo and story text'], membership: ['Heading', 'Membership: why join and how to join'], committee: ['Heading'] }
    for (const [page, titles] of Object.entries(cards)) {
      const w = mountPage(page)
      await flushPromises()
      expect(w.findAll('h3').map((h) => h.text())).toEqual(titles)
    }
  })

  it('says so for a page that does not exist', async () => {
    const wrapper = mountPage('nope')
    await flushPromises()
    expect(wrapper.text()).toContain('Page not found')
  })

  it('saves its headings and keeps the home page words', async () => {
    const wrapper = mountPage('contact')
    await flushPromises()
    await wrapper.get('input[aria-label="Contact: Title in your own language"]').setValue('যোগাযোগ')
    await wrapper.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()
    const sent = (mockUpdateAdminSettings.mock.calls[0][0] as { home_content: { headline: string; page_headings: Record<string, Record<string, string>> } }).home_content
    expect(sent.headline).toBe('Hello')
    expect(sent.page_headings.contact!.local_line).toBe('যোগাযোগ')
    expect(sent.page_headings.events!.title).toBe('What is on')
  })

  it('saves the gallery band: empty and coverage off by default, then what was typed', async () => {
    const wrapper = mountPage('gallery')
    await flushPromises()
    expect((wrapper.get('input[aria-label="Gallery band: show which years have photos"]').element as HTMLInputElement).checked).toBe(false)
    await wrapper.get('input[aria-label="Gallery band: Title"]').setValue('Old photos?')
    await wrapper.get('input[aria-label="Gallery band: show which years have photos"]').setValue(true)
    await wrapper.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()
    const sent = (mockUpdateAdminSettings.mock.calls[0][0] as { home_content: { gallery_band: Record<string, unknown> } }).home_content
    expect(sent.gallery_band).toMatchObject({ title: 'Old photos?', show_coverage: true, button_label: '' })
  })

  it('saves the news band (the Magazines tab is a module, not a check-box, since W8-R14)', async () => {
    const wrapper = mountPage('news')
    await flushPromises()
    expect(wrapper.find('input[aria-label="News: offer magazines"]').exists()).toBe(false)
    await wrapper.get('input[aria-label="News band: Title"]').setValue('The newsletter')
    await wrapper.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()
    const sent = (mockUpdateAdminSettings.mock.calls[0][0] as { home_content: { news_band: Record<string, unknown> } }).home_content
    expect(sent.news_band).toMatchObject({ title: 'The newsletter', consent: '' })
  })

  it('saves the contact questions: five empty rows, only a row with both question and answer is kept by the server', async () => {
    const wrapper = mountPage('contact')
    await flushPromises()
    expect(wrapper.findAll('input[aria-label^="Question"]')).toHaveLength(5)
    await wrapper.get('input[aria-label="Question 1"]').setValue('Where do you meet?')
    await wrapper.get('textarea[aria-label="Answer 1"]').setValue('At the hall.')
    await wrapper.get('input[aria-label="Contact: Link text to the membership page"]').setValue('Membership page')
    await wrapper.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()
    const sent = (mockUpdateAdminSettings.mock.calls[0][0] as { home_content: { contact_page: { faq: { title: string; content: string }[]; footnote_link: string } } }).home_content
    expect(sent.contact_page.faq[0]).toEqual({ title: 'Where do you meet?', content: 'At the hall.' })
    expect(sent.contact_page.footnote_link).toBe('Membership page')
  })

  it('saves the About sections: six card rows and ten timeline rows to fill, empty ones are dropped by the server', async () => {
    const wrapper = mountPage('about')
    await flushPromises()
    expect(wrapper.findAll('input[aria-label$="title"][aria-label^="Card"]')).toHaveLength(6)
    expect(wrapper.findAll('input[aria-label$="year"]')).toHaveLength(10)
    await wrapper.get('input[aria-label="Card 1 title"]').setValue('Community first')
    await wrapper.get('input[aria-label="Timeline 1 year"]').setValue('2010')
    await wrapper.get('input[aria-label="Timeline 1 title"]').setValue('We began')
    await wrapper.get('input[aria-label="About get involved: Title"]').setValue('Join us')
    await wrapper.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()
    const sent = (mockUpdateAdminSettings.mock.calls[0][0] as { home_content: { about_page: { values: { title: string }[]; timeline: { year: string; title: string }[]; involve_title: string } } }).home_content
    expect(sent.about_page.values[0]!.title).toBe('Community first')
    expect(sent.about_page.timeline[0]).toMatchObject({ year: '2010', title: 'We began' })
    expect(sent.about_page.involve_title).toBe('Join us')
  })

  it('saves the membership lists: six reasons and six steps to fill, empty rows dropped by the server', async () => {
    const wrapper = mountPage('membership')
    await flushPromises()
    expect(wrapper.findAll('input[aria-label^="Reason"]')).toHaveLength(6)
    expect(wrapper.findAll('input[aria-label^="Step"]')).toHaveLength(6)
    await wrapper.get('input[aria-label="Reason 1"]').setValue('Cheaper tickets')
    await wrapper.get('input[aria-label="Step 1"]').setValue('Create an account')
    await wrapper.get('input[aria-label="Membership: small line above the steps"]').setValue('How to join')
    await wrapper.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()
    const sent = (mockUpdateAdminSettings.mock.calls[0][0] as { home_content: { membership_page: { benefits: { text: string }[]; steps: { text: string }[]; steps_eyebrow: string } } }).home_content
    expect(sent.membership_page.benefits[0]!.text).toBe('Cheaper tickets')
    expect(sent.membership_page.steps[0]!.text).toBe('Create an account')
    expect(sent.membership_page.steps_eyebrow).toBe('How to join')
  })
})
