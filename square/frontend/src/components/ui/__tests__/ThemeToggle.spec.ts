// Tests for ThemeToggle (3 cases), e.g. ThemeToggle; toggles light -> dark -> light on click; labels the button with the theme it will switch to.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ThemeToggle from '../ThemeToggle.vue'
import { useTheme } from '../../../composables/useTheme'

beforeEach(() => {
  localStorage.clear()
  document.documentElement.classList.remove('dark')
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  )
  const { setTheme } = useTheme()
  setTheme('light')
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ThemeToggle', () => {
  it('toggles light -> dark -> light on click', async () => {
    const wrapper = mount(ThemeToggle)
    const { theme } = useTheme()

    expect(theme.value).toBe('light')

    await wrapper.find('button').trigger('click')
    expect(theme.value).toBe('dark')

    await wrapper.find('button').trigger('click')
    expect(theme.value).toBe('light')
  })

  it('labels the button with the theme it will switch to', async () => {
    const wrapper = mount(ThemeToggle)

    expect(wrapper.find('button').attributes('aria-label')).toBe('Switch to dark theme')
    expect(wrapper.text()).toContain('Dark')

    await wrapper.find('button').trigger('click')

    expect(wrapper.find('button').attributes('aria-label')).toBe('Switch to light theme')
    expect(wrapper.text()).toContain('Light')
  })
})
