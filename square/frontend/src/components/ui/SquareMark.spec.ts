// Tests for SquareMark (4 cases), e.g. SquareMark; shows the first letter when the square has no logo; shows the square's logo when it has one (W6-R53).
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

const profile = vi.hoisted(() => ({ name: 'First Org', logoUrl: '', logoDarkUrl: '' }))
vi.mock('../../services/squareConfig', () => ({ squareProfile: profile }))

import SquareMark from './SquareMark.vue'
import { useTheme } from '../../composables/useTheme'

describe('SquareMark', () => {
  it('shows the first letter when the square has no logo', () => {
    profile.logoUrl = ''
    profile.logoDarkUrl = ''
    const wrapper = mount(SquareMark)
    expect(wrapper.text()).toBe('F')
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it("shows the square's logo when it has one (W6-R53)", () => {
    profile.logoUrl = 'https://files.example/logo.png'
    const wrapper = mount(SquareMark, { props: { size: 44 } })
    expect(wrapper.get('img').attributes('src')).toBe('https://files.example/logo.png')
    expect(wrapper.text()).toBe('')
  })

  it('uses the dark logo on dark backgrounds and the light one elsewhere, each standing in for a missing other (W6-R65)', () => {
    profile.logoUrl = 'https://files.example/light.png'
    profile.logoDarkUrl = 'https://files.example/dark.png'
    useTheme().setTheme('light')
    expect(mount(SquareMark).get('img').attributes('src')).toBe('https://files.example/light.png')
    expect(mount(SquareMark, { props: { onDark: true } }).get('img').attributes('src')).toBe('https://files.example/dark.png')
    useTheme().setTheme('dark')
    expect(mount(SquareMark).get('img').attributes('src')).toBe('https://files.example/dark.png')
    profile.logoDarkUrl = ''
    expect(mount(SquareMark, { props: { onDark: true } }).get('img').attributes('src')).toBe('https://files.example/light.png')
    profile.logoUrl = ''
    profile.logoDarkUrl = 'https://files.example/dark.png'
    useTheme().setTheme('light')
    expect(mount(SquareMark).get('img').attributes('src')).toBe('https://files.example/dark.png')
  })
})
