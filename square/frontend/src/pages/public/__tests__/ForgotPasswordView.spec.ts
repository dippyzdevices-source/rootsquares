// Tests for ForgotPasswordView (3 cases), e.g. ForgotPasswordView; calls requestPasswordReset with the entered email; shows a success message after requesting a reset.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const mockResetPasswordForEmail = vi.fn()

vi.mock('../../../services/supabaseClient', () => ({
  supabase: {
    auth: { resetPasswordForEmail: (...args: unknown[]) => mockResetPasswordForEmail(...args) },
  },
}))

import ForgotPasswordView from '../ForgotPasswordView.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('ForgotPasswordView', () => {
  it('calls requestPasswordReset with the entered email', async () => {
    mockResetPasswordForEmail.mockResolvedValue({ error: null })
    const wrapper = mount(ForgotPasswordView)

    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('button').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(mockResetPasswordForEmail).toHaveBeenCalledWith(
      'a@b.com',
      expect.objectContaining({ redirectTo: expect.stringContaining('/reset-password') }),
    )
  })

  it('shows a success message after requesting a reset', async () => {
    mockResetPasswordForEmail.mockResolvedValue({ error: null })
    const wrapper = mount(ForgotPasswordView)

    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('button').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Check your email')
  })
})
