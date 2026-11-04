// Tests for ResetPasswordView (3 cases), e.g. ResetPasswordView; calls updatePassword with the entered password; shows an error message when the update fails.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'

const mockUpdateUser = vi.fn()

vi.mock('../../../services/supabaseClient', () => ({
  supabase: { auth: { updateUser: (...args: unknown[]) => mockUpdateUser(...args) } },
}))

import ResetPasswordView from '../ResetPasswordView.vue'

function mountView() {
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/login', component: { template: '<div/>' } },
    ],
  })
  return mount(ResetPasswordView, { global: { plugins: [router] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('ResetPasswordView', () => {
  it('calls updatePassword with the entered password', async () => {
    mockUpdateUser.mockResolvedValue({ error: null })
    const wrapper = mountView()

    await wrapper.find('input[type="password"]').setValue('newSecret123')
    await wrapper.find('button').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(mockUpdateUser).toHaveBeenCalledWith({ password: 'newSecret123' })
  })

  it('shows an error message when the update fails', async () => {
    mockUpdateUser.mockResolvedValue({ error: new Error('Session expired') })
    const wrapper = mountView()

    await wrapper.find('input[type="password"]').setValue('newSecret123')
    await wrapper.find('button').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Session expired')
  })
})
