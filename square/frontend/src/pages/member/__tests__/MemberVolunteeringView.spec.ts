// Tests for MemberVolunteeringView (4 cases), e.g. MemberVolunteeringView; splits assignments into upcoming and past sections; shows an empty state when there are no assignments at all.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchMyTaskAssignments = vi.fn()

vi.mock('../../../services/memberApi', () => ({
  fetchMyTaskAssignments: (...args: unknown[]) => mockFetchMyTaskAssignments(...args),
}))

import MemberVolunteeringView from '../MemberVolunteeringView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

beforeEach(() => {
  vi.clearAllMocks()
})

describe('MemberVolunteeringView', () => {
  it('splits assignments into upcoming and past sections', async () => {
    mockFetchMyTaskAssignments.mockResolvedValue([
      {
        id: 1, category: 'food', event_id: 1, event_title: 'Durga Puja 2026',
        event_slug: 'durga-puja-2026', event_start_datetime: '2099-10-10T10:00:00Z', event_end_datetime: null,
      },
      {
        id: 2, category: 'decoration', event_id: 2, event_title: 'Saraswati Puja 2020',
        event_slug: 'saraswati-puja-2020', event_start_datetime: '2020-01-01T10:00:00Z', event_end_datetime: null,
      },
    ])

    const wrapper = mount(MemberVolunteeringView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Upcoming')
    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.text()).toContain('Food')
    expect(wrapper.text()).toContain('Past')
    expect(wrapper.text()).toContain('Saraswati Puja 2020')
    expect(wrapper.text()).toContain('Decoration')
  })

  it('shows an empty state when there are no assignments at all', async () => {
    mockFetchMyTaskAssignments.mockResolvedValue([])

    const wrapper = mount(MemberVolunteeringView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('No volunteering assigned yet')
  })

  it('shows an error state when the fetch fails', async () => {
    mockFetchMyTaskAssignments.mockRejectedValue(new Error('network error'))

    const wrapper = mount(MemberVolunteeringView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain("Couldn't load your volunteering history")
  })
})
