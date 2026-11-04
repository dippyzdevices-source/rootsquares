// Tests for TestimonialSubmitView (6 cases), e.g. TestimonialSubmitView; submits the story and shows a pending-review confirmation; includes optional context and photo URL when given.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockSubmitTestimonial = vi.fn()

vi.mock('../../../services/testimonialsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/testimonialsApi')>(
    '../../../services/testimonialsApi',
  )
  return {
    ...actual,
    submitTestimonial: (...args: unknown[]) => mockSubmitTestimonial(...args),
  }
})

import TestimonialSubmitView from '../TestimonialSubmitView.vue'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('TestimonialSubmitView', () => {
  it('submits the story and shows a pending-review confirmation', async () => {
    mockSubmitTestimonial.mockResolvedValue({ id: 1, status: 'pending' })

    const wrapper = mount(TestimonialSubmitView)

    await wrapper.find('textarea').setValue('BCA Oslo feels like family.')
    await wrapper.find('input[placeholder="Your full name"]').setValue('Priya Das')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(mockSubmitTestimonial).toHaveBeenCalledWith({
      quote: 'BCA Oslo feels like family.',
      author_name: 'Priya Das',
      author_context: null,
      photo_url: null,
    })
    expect(wrapper.text()).toContain('sent for review')
  })

  it('includes optional context and photo URL when given', async () => {
    mockSubmitTestimonial.mockResolvedValue({ id: 1, status: 'pending' })

    const wrapper = mount(TestimonialSubmitView)

    await wrapper.find('textarea').setValue('Great community.')
    await wrapper.find('input[placeholder="Your full name"]').setValue('Rohan Sen')
    await wrapper.find('input[placeholder="Member since 2020"]').setValue('Member since 2022')
    await wrapper.find('input[placeholder="https://…"]').setValue('https://example.com/me.jpg')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(mockSubmitTestimonial).toHaveBeenCalledWith({
      quote: 'Great community.',
      author_name: 'Rohan Sen',
      author_context: 'Member since 2022',
      photo_url: 'https://example.com/me.jpg',
    })
  })

  it('shows validation errors from the API without a generic error message', async () => {
    const { ValidationError } = await vi.importActual<typeof import('../../../services/testimonialsApi')>(
      '../../../services/testimonialsApi',
    )
    mockSubmitTestimonial.mockRejectedValue(new ValidationError({ author_name: 'This field is required.' }))

    const wrapper = mount(TestimonialSubmitView)
    await wrapper.find('textarea').setValue('Great community.')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('This field is required.')
    expect(wrapper.text()).not.toContain('Not quite ready to send')
  })

  it('shows a generic error when the request itself fails', async () => {
    mockSubmitTestimonial.mockRejectedValue(new Error('Network error'))

    const wrapper = mount(TestimonialSubmitView)
    await wrapper.find('textarea').setValue('Great community.')
    await wrapper.find('input[placeholder="Your full name"]').setValue('Rohan Sen')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Not quite ready to send')
  })

  it('lets the visitor share another story after a successful submission', async () => {
    mockSubmitTestimonial.mockResolvedValue({ id: 1, status: 'pending' })

    const wrapper = mount(TestimonialSubmitView)
    await wrapper.find('textarea').setValue('Great community.')
    await wrapper.find('input[placeholder="Your full name"]').setValue('Rohan Sen')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Share another')
    await wrapper.findAll('button').find((b) => b.text() === 'Share another')!.trigger('click')

    expect(wrapper.find('textarea').exists()).toBe(true)
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('')
  })
})
