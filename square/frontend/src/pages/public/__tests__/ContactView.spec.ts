// Tests for ContactView (12 cases), e.g. ContactView; shows the fetched contact details; renders without error when the fetch fails.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { selectedLabel } from '../../../test-utils/baseSelect'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchSettings = vi.fn()
const mockSubmitContactForm = vi.fn()
const mockRoute = { query: {} as Record<string, string> }

// The reasons are the square's own list (W7-R9); this square offers three.
vi.mock('../../../services/lookupsApi', () => ({
  fetchLookup: async (key: string) =>
    key === 'contact_reason'
      ? [
          { value: 'general', label: 'General enquiry' },
          { value: 'photos', label: 'Contribute photographs' },
          { value: 'press', label: 'Press' },
        ]
      : [],
}))

const mockHomeContent = vi.fn()
vi.mock('../../../services/siteContent', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/siteContent')>()),
  loadHomeContent: () => mockHomeContent(),
}))

vi.mock('vue-router', () => ({ useRoute: () => mockRoute }))

vi.mock('../../../services/settingsApi', () => ({
  fetchSettings: (...args: unknown[]) => mockFetchSettings(...args),
}))

vi.mock('../../../services/contactApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/contactApi')>('../../../services/contactApi')
  return {
    ...actual,
    submitContactForm: (...args: unknown[]) => mockSubmitContactForm(...args),
  }
})

import { fillHomeContent } from '../../../services/siteContent'
import ContactView from '../ContactView.vue'
import { ValidationError } from '../../../services/contactApi'

beforeEach(() => {
  mockRoute.query = {}
  vi.clearAllMocks()
  mockHomeContent.mockResolvedValue(fillHomeContent(undefined))
  mockFetchSettings.mockResolvedValue({
    contact_email: 'hello@bcaoslo.no',
    contact_phone: '+47 123 45 678',
    contact_address: 'Oslo, Norway',
  })
})

async function fillValidForm(wrapper: ReturnType<typeof mount>) {
  await wrapper.find('input[type="text"]').setValue('Priya Das')
  await wrapper.find('input[type="email"]').setValue('priya@example.com')
  await wrapper.find('textarea').setValue('I would like to know more about membership options here.')
  await wrapper.find('input[type="checkbox"]').setValue(true)
}

describe('ContactView', () => {
  it('shows the fetched contact details', async () => {
    const wrapper = mount(ContactView)
    await flushPromises()

    expect(wrapper.text()).toContain('hello@bcaoslo.no')
    expect(wrapper.text()).toContain('+47 123 45 678')
    expect(wrapper.text()).toContain('Oslo, Norway')
    expect(wrapper.find('a[href="mailto:hello@bcaoslo.no"]').exists()).toBe(true)
  })

  it('renders without error when the fetch fails', async () => {
    mockFetchSettings.mockRejectedValue(new Error('boom'))

    const wrapper = mount(ContactView)
    await flushPromises()

    expect(wrapper.text()).toContain('Contact us')
  })

  it('submits the form to the backend and shows a success message', async () => {
    mockSubmitContactForm.mockResolvedValue({ success: true, message: 'Your message has been sent successfully.' })

    const wrapper = mount(ContactView)
    await flushPromises()
    await fillValidForm(wrapper)
    await wrapper.find('button.ds-btn').trigger('click')
    await flushPromises()

    expect(mockSubmitContactForm).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Priya Das', email: 'priya@example.com' })
    )
    expect(wrapper.text()).toContain('Message sent')
  })

  it('shows field validation errors from the backend without clearing entered values', async () => {
    mockSubmitContactForm.mockRejectedValue(new ValidationError({ message: 'Must be at least 10 characters.' }))

    const wrapper = mount(ContactView)
    await flushPromises()
    await fillValidForm(wrapper)
    await wrapper.find('button.ds-btn').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Must be at least 10 characters.')
    expect((wrapper.find('input[type="text"]').element as HTMLInputElement).value).toBe('Priya Das')
  })

  it('shows a friendly error when the backend is unavailable', async () => {
    mockSubmitContactForm.mockRejectedValue(new Error("We couldn't send your message right now. Please try again later."))

    const wrapper = mount(ContactView)
    await flushPromises()
    await fillValidForm(wrapper)
    await wrapper.find('button.ds-btn').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain("We couldn't send your message right now. Please try again later.")
  })

  it('preselects "Contribute photographs" and prefills a starter message for ?reason=photos', async () => {
    mockRoute.query = { reason: 'photos' }
    mockFetchSettings.mockResolvedValue({ contact_email: '', contact_phone: '', contact_address: '' })
    const wrapper = mount(ContactView)
    await flushPromises()

    expect(selectedLabel(wrapper)).toBe('Contribute photographs')
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toContain('I have photographs from')
  })

  it('loads the map only after "Show map", and always offers Open in Maps and Get directions', async () => {
    mockFetchSettings.mockResolvedValue({
      contact_email: 'hello@bcaoslo.no',
      contact_phone: '+47 123 45 678',
      contact_address: 'c/o Niladri Malakar, Bølerlia 6, 0691 OSLO',
    })
    const wrapper = mount(ContactView)
    await flushPromises()

    expect(wrapper.find('iframe').exists()).toBe(false)
    const q = encodeURIComponent('Bølerlia 6, 0691 OSLO')
    expect(wrapper.find('a.open-map').attributes('href')).toBe(`https://www.google.com/maps/search/?api=1&query=${q}`)
    expect(wrapper.find('a.map-directions').attributes('href')).toBe(`https://www.google.com/maps/dir/?api=1&destination=${q}`)

    await wrapper.find('button.show-map').trigger('click')
    const frame = wrapper.find('iframe')
    expect(frame.exists()).toBe(true)
    expect(frame.attributes('src')).toBe(`https://maps.google.com/maps?q=${q}&output=embed`)
  })

  it('shows no map controls when no address is configured', async () => {
    mockFetchSettings.mockResolvedValue({ contact_email: '', contact_phone: '', contact_address: '' })
    const wrapper = mount(ContactView)
    await flushPromises()
    expect(wrapper.find('button.show-map').exists()).toBe(false)
    expect(wrapper.find('a.open-map').exists()).toBe(false)
  })

  it('shows no questions section and no footnote until the square sets them (W7-R9)', async () => {
    const wrapper = mount(ContactView)
    await flushPromises()

    expect(wrapper.find('.ds-accordion').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Asked most often')
    expect(wrapper.find('a[href="/membership"]').exists()).toBe(false)
  })

  it("shows the square's own questions and footnote", async () => {
    mockHomeContent.mockResolvedValue(
      fillHomeContent({
        contact_page: {
          faq_eyebrow: 'Before you write',
          faq_title: 'Common questions',
          faq: [{ title: 'Where do you meet?', content: 'At the hall.' }],
          footnote_text: 'Joining?',
          footnote_link: 'Membership page',
        },
      }),
    )
    const wrapper = mount(ContactView, { global: { stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } } })
    await flushPromises()

    expect(wrapper.text()).toContain('Common questions')
    expect(wrapper.text()).toContain('Where do you meet?')
    expect(wrapper.text()).toContain('At the hall.')
    expect(wrapper.text()).toContain('Joining?')
    expect(wrapper.find('a[href="/membership"]').text()).toBe('Membership page')
  })

  it('offers the squares own reasons, sends the chosen label as the subject, and falls back to the first for an unknown ?reason', async () => {
    mockRoute.query = { reason: 'nope' }
    mockSubmitContactForm.mockResolvedValue({ success: true })
    const wrapper = mount(ContactView)
    await flushPromises()
    expect(selectedLabel(wrapper)).toBe('General enquiry')

    await fillValidForm(wrapper)
    await wrapper.find('button.ds-btn').trigger('click')
    await flushPromises()
    expect(mockSubmitContactForm).toHaveBeenCalledWith(expect.objectContaining({ subject: 'General enquiry' }))
  })
})
