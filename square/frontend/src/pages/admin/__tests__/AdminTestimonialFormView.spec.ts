// Tests for AdminTestimonialFormView (3 cases), e.g. AdminTestimonialFormView; creates a new testimonial; shows validation errors from the API.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAdminTestimonial = vi.fn()
const mockCreateAdminTestimonial = vi.fn()
const mockUpdateAdminTestimonial = vi.fn()

vi.mock('../../../services/adminTestimonialsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminTestimonialsApi')>(
    '../../../services/adminTestimonialsApi',
  )
  return {
    ...actual,
    fetchAdminTestimonial: (...args: unknown[]) => mockFetchAdminTestimonial(...args),
    createAdminTestimonial: (...args: unknown[]) => mockCreateAdminTestimonial(...args),
    updateAdminTestimonial: (...args: unknown[]) => mockUpdateAdminTestimonial(...args),
  }
})

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {} }),
  useRouter: () => ({ push: mockPush }),
}))

import AdminTestimonialFormView from '../AdminTestimonialFormView.vue'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AdminTestimonialFormView', () => {
  it('creates a new testimonial', async () => {
    mockCreateAdminTestimonial.mockResolvedValue({ id: 1 })

    const wrapper = mount(AdminTestimonialFormView)
    await flushPromises()

    await wrapper.find('textarea').setValue('Great community.')
    await wrapper.find('input[placeholder="Priya Das"]').setValue('Rohan Sen')
    await wrapper.find('button.save-testimonial').trigger('click')
    await flushPromises()

    expect(mockCreateAdminTestimonial).toHaveBeenCalledWith(
      expect.objectContaining({ quote: 'Great community.', author_name: 'Rohan Sen' }),
    )
  })

  it('shows validation errors from the API', async () => {
    const { ValidationError } = await vi.importActual<typeof import('../../../services/adminTestimonialsApi')>(
      '../../../services/adminTestimonialsApi',
    )
    mockCreateAdminTestimonial.mockRejectedValue(new ValidationError({ author_name: 'This field is required.' }))

    const wrapper = mount(AdminTestimonialFormView)
    await flushPromises()

    await wrapper.find('button.save-testimonial').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('This field is required.')
  })
})
