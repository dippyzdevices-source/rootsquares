// Tests for UpgradeLink (2 cases): the way up from a locked feature (W26-R17) asks the reader to tell the owner; the button shows only when the server told the browser the platform's address.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

const profile = vi.hoisted(() => ({ platformUrl: '' }))
vi.mock('../../services/squareConfig', () => ({ squareProfile: profile }))
import UpgradeLink from '../UpgradeLink.vue'

describe('UpgradeLink', () => {
  beforeEach(() => { profile.platformUrl = '' })

  it('tells the reader to ask the owner, without a button, when the platform address is not known', () => {
    const w = mount(UpgradeLink)
    expect(w.text()).toContain('Ask the owner of this square to upgrade the plan')
    expect(w.find('a').exists()).toBe(false)
  })

  it('links to the platform dashboard in a new tab when it is known', () => {
    profile.platformUrl = 'https://rootsquares.example'
    const a = mount(UpgradeLink).find('a')
    expect(a.attributes('href')).toBe('https://rootsquares.example/dashboard')
    expect(a.attributes('target')).toBe('_blank')
    expect(a.attributes('rel')).toContain('noopener')
  })
})
