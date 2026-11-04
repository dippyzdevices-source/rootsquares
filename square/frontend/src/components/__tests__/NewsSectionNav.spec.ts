// Tests for NewsSectionNav (3 cases), e.g. NewsSectionNav; has Articles and Magazines when the module is on; has only Articles when the module is off.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

// The Magazines tab of the admin News area belongs to the Magazines module (W8-R14).
const off = vi.hoisted(() => ({ keys: [] as string[] }))
vi.mock('../../services/modules', () => ({ moduleEnabled: (key?: string) => !off.keys.includes(key ?? '') }))

import NewsSectionNav from '../NewsSectionNav.vue'

const stub = { SectionTabs: { props: ['tabs'], template: '<ul><li v-for="t in tabs" :key="t.to">{{ t.label }}</li></ul>' } }

beforeEach(() => {
  off.keys = []
})

describe('NewsSectionNav', () => {
  it('has Articles and Magazines when the module is on', () => {
    expect(mount(NewsSectionNav, { global: { stubs: stub } }).findAll('li').map((l) => l.text())).toEqual(['Articles', 'Magazines'])
  })

  it('has only Articles when the module is off', () => {
    off.keys = ['magazines']
    expect(mount(NewsSectionNav, { global: { stubs: stub } }).findAll('li').map((l) => l.text())).toEqual(['Articles'])
  })
})
