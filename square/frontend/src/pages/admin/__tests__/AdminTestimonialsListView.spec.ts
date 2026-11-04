// Tests for AdminTestimonialsListView (12 cases), e.g. AdminTestimonialsListView; shows testimonials with their moderation status; pre-selects the status filter from a ?status= query param.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockFetchAdminTestimonials = vi.fn()
const mockDeleteAdminTestimonial = vi.fn()
const mockUpdateAdminTestimonial = vi.fn()

vi.mock('../../../services/adminTestimonialsApi', () => ({
  fetchAdminTestimonials: (...args: unknown[]) => mockFetchAdminTestimonials(...args),
  deleteAdminTestimonial: (...args: unknown[]) => mockDeleteAdminTestimonial(...args),
  updateAdminTestimonial: (...args: unknown[]) => mockUpdateAdminTestimonial(...args),
}))

// Bare object rather than a real router — this view only reads `route.query` (never
// navigates), matching this codebase's convention for components using the bare
// `<router-link>` tag rather than an imported `RouterLink`.
const mockRoute: { query: Record<string, string> } = { query: {} }
vi.mock('vue-router', () => ({ useRoute: () => mockRoute }))

import AdminTestimonialsListView from '../AdminTestimonialsListView.vue'

const stubs = { RouterLink: true }

beforeEach(() => {
  vi.clearAllMocks()
  mockRoute.query = {}
})

const baseTestimonial = {
  id: 1,
  quote: 'BCA Oslo feels like family.',
  author_name: 'Priya Das',
  author_context: null,
  photo_url: null,
  sort_order: 0,
  is_active: true,
  status: 'approved',
  created_at: '',
  updated_at: '',
}

describe('AdminTestimonialsListView', () => {
  it('shows testimonials with their moderation status', async () => {
    mockFetchAdminTestimonials.mockResolvedValue({
      items: [
        { ...baseTestimonial, status: 'approved' },
        { ...baseTestimonial, id: 2, author_name: 'Rohan Sen', status: 'pending', is_active: false },
      ],
      page: 1, per_page: 20, total: 2, total_pages: 1,
    })

    const wrapper = mount(AdminTestimonialsListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('Approved')
    expect(wrapper.text()).toContain('Rohan Sen')
    expect(wrapper.text()).toContain('Pending')
  })

  it('pre-selects the status filter from a ?status= query param', async () => {
    mockRoute.query = { status: 'pending' }
    mockFetchAdminTestimonials.mockResolvedValue({
      items: [{ ...baseTestimonial, id: 2, author_name: 'Rohan Sen', status: 'pending', is_active: false }],
      page: 1, per_page: 20, total: 1, total_pages: 1,
    })

    const wrapper = mount(AdminTestimonialsListView, { global: { stubs } })
    await flushPromises()

    expect(mockFetchAdminTestimonials).toHaveBeenCalledWith('pending', 20, 1, undefined)
    expect(wrapper.find('.ds-tag-selected').text()).toBe('Pending review')
  })

  it('shows an empty state when there are no testimonials', async () => {
    mockFetchAdminTestimonials.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 })

    const wrapper = mount(AdminTestimonialsListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('No testimonials yet')
  })

  it('deletes a testimonial after confirming', async () => {
    mockFetchAdminTestimonials.mockResolvedValue({ items: [baseTestimonial], page: 1, per_page: 20, total: 1, total_pages: 1 })
    mockDeleteAdminTestimonial.mockResolvedValue(undefined)

    const wrapper = mount(AdminTestimonialsListView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('button[aria-label="Delete testimonial from Priya Das"]').trigger('click')

    const body = new DOMWrapper(document.body)
    await body.findAll('button').find((b) => b.text() === 'Delete')!.trigger('click')
    await flushPromises()

    expect(mockDeleteAdminTestimonial).toHaveBeenCalledWith(1)

    wrapper.unmount()
  })

  it('reloads with a status filter when a filter tag is clicked', async () => {
    mockFetchAdminTestimonials.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 })

    const wrapper = mount(AdminTestimonialsListView, { global: { stubs } })
    await flushPromises()
    mockFetchAdminTestimonials.mockClear()

    await wrapper.findAll('button').find((b) => b.text() === 'Pending review')!.trigger('click')
    await flushPromises()

    expect(mockFetchAdminTestimonials).toHaveBeenCalledWith('pending', 20, 1, undefined)
  })

  it('only shows Approve/Reject actions for a pending testimonial', async () => {
    mockFetchAdminTestimonials.mockResolvedValue({
      items: [
        { ...baseTestimonial, id: 1, status: 'approved' },
        { ...baseTestimonial, id: 2, status: 'pending' },
      ],
      page: 1, per_page: 20, total: 2, total_pages: 1,
    })

    const wrapper = mount(AdminTestimonialsListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.findAll('button[aria-label^="Approve testimonial"]')).toHaveLength(1)
    expect(wrapper.findAll('button[aria-label^="Reject testimonial"]')).toHaveLength(1)
  })

  it('approves a pending testimonial', async () => {
    mockFetchAdminTestimonials.mockResolvedValue({
      items: [{ ...baseTestimonial, status: 'pending', is_active: false }],
      page: 1, per_page: 20, total: 1, total_pages: 1,
    })
    mockUpdateAdminTestimonial.mockResolvedValue({ ...baseTestimonial, status: 'approved', is_active: true })

    const wrapper = mount(AdminTestimonialsListView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('button[aria-label="Approve testimonial from Priya Das"]').trigger('click')
    await flushPromises()

    expect(mockUpdateAdminTestimonial).toHaveBeenCalledWith(1, { status: 'approved', is_active: true })
  })

  it('rejects a pending testimonial', async () => {
    mockFetchAdminTestimonials.mockResolvedValue({
      items: [{ ...baseTestimonial, status: 'pending', is_active: false }],
      page: 1, per_page: 20, total: 1, total_pages: 1,
    })
    mockUpdateAdminTestimonial.mockResolvedValue({ ...baseTestimonial, status: 'rejected' })

    const wrapper = mount(AdminTestimonialsListView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('button[aria-label="Reject testimonial from Priya Das"]').trigger('click')
    await flushPromises()

    expect(mockUpdateAdminTestimonial).toHaveBeenCalledWith(1, { status: 'rejected', is_active: false })
  })

  it('shows the homepage display order for each testimonial', async () => {
    mockFetchAdminTestimonials.mockResolvedValue({
      items: [{ ...baseTestimonial, sort_order: 3 }],
      page: 1, per_page: 20, total: 1, total_pages: 1,
    })

    const wrapper = mount(AdminTestimonialsListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Order')
    expect(wrapper.find('td').exists()).toBe(true)
    expect(wrapper.text()).toContain('3')
  })

  it('opens a read-only view of the full testimonial without navigating to edit', async () => {
    mockFetchAdminTestimonials.mockResolvedValue({
      items: [{ ...baseTestimonial, quote: 'A much longer quote than the truncated table cell shows in full.' }],
      page: 1, per_page: 20, total: 1, total_pages: 1,
    })

    const wrapper = mount(AdminTestimonialsListView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('button[aria-label="View testimonial from Priya Das"]').trigger('click')
    await flushPromises()

    const body = new DOMWrapper(document.body)
    expect(body.text()).toContain('A much longer quote than the truncated table cell shows in full.')
    expect(body.text()).toContain('Homepage display order')

    wrapper.unmount()
  })

  it('searches testimonials by name or quote, together with the status pill', async () => {
    mockFetchAdminTestimonials.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 1 })
    const wrapper = mount(AdminTestimonialsListView, { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
    await flushPromises()
    mockFetchAdminTestimonials.mockClear()

    await wrapper.findAll('.ds-toolbar-pills .ds-tag').find((b) => b.text() === 'Pending review')!.trigger('click')
    await wrapper.find('input[type="search"]').setValue('durga')
    await wrapper.find('input[type="search"]').trigger('keyup', { key: 'Enter' })
    await flushPromises()

    expect(mockFetchAdminTestimonials).toHaveBeenLastCalledWith('pending', 20, 1, 'durga')
  })
})
