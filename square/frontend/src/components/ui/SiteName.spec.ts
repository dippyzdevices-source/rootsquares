// Tests for SiteName (5 cases), e.g. SiteName (W6-R67); writes the name as it is by default; writes capitals with a dot between the words, with the light or the go.
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

const profile = vi.hoisted(() => ({ name: 'BCA Oslo' }))
vi.mock('../../services/squareConfig', () => ({ squareProfile: profile }))

import SiteName from './SiteName.vue'
import { logoHeight } from '../../services/siteContent'

describe('SiteName (W6-R67)', () => {
  it('writes the name as it is by default', () => {
    expect(mount(SiteName).text()).toBe('BCA Oslo')
    expect(mount(SiteName, { props: { variant: 'plain' } }).text()).toBe('BCA Oslo')
  })

  it('writes capitals with a dot between the words, with the light or the gold dot', () => {
    const light = mount(SiteName, { props: { variant: 'caps' } })
    expect(light.text()).toBe('BCA·OSLO')
    expect(light.find('.ds-wordmark-dot').exists()).toBe(true)
    const dark = mount(SiteName, { props: { variant: 'caps', onDark: true } })
    expect(dark.find('.ds-wordmark-dot-dark').exists()).toBe(true)
    expect(dark.classes()).toContain('ds-wordmark-onDark')
  })

  it('leaves a one-word name alone', () => {
    profile.name = 'rootsquares'
    expect(mount(SiteName, { props: { variant: 'caps' } }).text()).toBe('rootsquares')
    profile.name = 'BCA Oslo'
  })

  it('maps the logo sizes to heights, medium by default', () => {
    expect([logoHeight(''), logoHeight('small'), logoHeight('medium'), logoHeight('large')]).toEqual([44, 32, 44, 64])
  })
})
