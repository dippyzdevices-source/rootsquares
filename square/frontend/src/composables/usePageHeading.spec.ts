// Tests for usePageHeading (3 cases), e.g. usePageHeading (W6-R75); gives the neutral text until the square sets its own, key by key; leaves another page alone.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'

const mockLoadHomeContent = vi.fn()
vi.mock('../services/siteContent', async () => {
  const actual = await vi.importActual<typeof import('../services/siteContent')>('../services/siteContent')
  return { ...actual, loadHomeContent: () => mockLoadHomeContent() }
})

import { usePageHeading } from './usePageHeading'
import { EMPTY_HOME_CONTENT } from '../services/siteContent'

function heading(defaults: Parameters<typeof usePageHeading>[1]) {
  let result!: ReturnType<typeof usePageHeading>
  mount(defineComponent({ setup() { result = usePageHeading('events', defaults); return () => h('div') } }))
  return () => result.value
}

beforeEach(() => vi.clearAllMocks())

describe('usePageHeading (W6-R75)', () => {
  it('gives the neutral text until the square sets its own, key by key', async () => {
    mockLoadHomeContent.mockResolvedValue({ ...EMPTY_HOME_CONTENT, page_headings: { events: { title: 'What is on', local_line: 'কর্মসূচি' } } })
    const current = heading(() => ({ eyebrow: 'Programme', title: 'Events', intro: 'Upcoming and past.' }))
    expect(current()).toEqual({ eyebrow: 'Programme', script_line: '', title: 'Events', local_line: '', intro: 'Upcoming and past.', nav_label: '' })
    await flushPromises()
    expect(current()).toEqual({ eyebrow: 'Programme', script_line: '', title: 'What is on', local_line: 'কর্মসূচি', intro: 'Upcoming and past.', nav_label: '' })
  })

  it('leaves another page alone', async () => {
    mockLoadHomeContent.mockResolvedValue({ ...EMPTY_HOME_CONTENT, page_headings: { gallery: { title: 'Pictures' } } })
    const current = heading({ title: 'Events' })
    await flushPromises()
    expect(current().title).toBe('Events')
  })
})
