// Tests for CommitteeView (8 cases), e.g. CommitteeView; shows committee members with their role, quote, and address; shows email/phone as clickable links and the member-since year, when p.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchCommittee = vi.fn()

vi.mock('../../../services/committeeApi', () => ({
  fetchCommittee: (...args: unknown[]) => mockFetchCommittee(...args),
}))

import CommitteeView from '../CommitteeView.vue'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('CommitteeView', () => {
  it('shows committee members with their role, quote, and address', async () => {
    mockFetchCommittee.mockResolvedValue({
      items: [
        {
          id: 1,
          name: 'Priya Das',
          role: 'President',
          portrait_url: null,
          address: 'Oslo, Norway',
          email: null,
          phone: null,
          member_since: null,
          quote: 'Leads the association.',
        },
      ],
    })

    const wrapper = mount(CommitteeView)
    await flushPromises()

    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('President')
    expect(wrapper.text()).toContain('Leads the association.')
    expect(wrapper.text()).toContain('Oslo, Norway')
  })

  it('shows email/phone as clickable links and the member-since year, when present', async () => {
    mockFetchCommittee.mockResolvedValue({
      items: [
        {
          id: 1,
          name: 'Sujata Bose',
          role: 'Chair',
          portrait_url: null,
          address: null,
          email: 'chair@bcaoslo.no',
          phone: '+47 401 22 318',
          member_since: 1994,
          quote: null,
        },
      ],
    })

    const wrapper = mount(CommitteeView)
    await flushPromises()

    expect(wrapper.find('a[href="mailto:chair@bcaoslo.no"]').text()).toBe('chair@bcaoslo.no')
    expect(wrapper.find('a[href="tel:+4740122318"]').text()).toBe('+47 401 22 318')
    expect(wrapper.text()).toContain('Member since 1994')
  })

  it('shows the sub-name under the name only when set', async () => {
    mockFetchCommittee.mockResolvedValue({
      items: [
        { id: 1, name: 'Priya Das', sub_name: 'প্রিয়া দাস', role: 'President', portrait_url: null, address: null, email: null, phone: null, member_since: null, quote: null },
        { id: 2, name: 'Arun Sen', sub_name: null, role: 'Treasurer', portrait_url: null, address: null, email: null, phone: null, member_since: null, quote: null },
      ],
    })

    const wrapper = mount(CommitteeView)
    await flushPromises()

    const subs = wrapper.findAll('.ds-portrait-subname')
    expect(subs).toHaveLength(1)
    expect(subs[0].text()).toBe('প্রিয়া দাস')
  })

  it('falls back to a placeholder frame when a member has no portrait', async () => {
    mockFetchCommittee.mockResolvedValue({
      items: [{
        id: 1, name: 'Priya Das', role: 'President', portrait_url: null, address: null,
        email: null, phone: null, member_since: null, quote: null,
      }],
    })

    const wrapper = mount(CommitteeView)
    await flushPromises()

    expect(wrapper.find('.ds-placeholder').exists()).toBe(true)
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('shows an empty state when there are no committee members', async () => {
    mockFetchCommittee.mockResolvedValue({ items: [] })

    const wrapper = mount(CommitteeView)
    await flushPromises()

    expect(wrapper.text()).toContain('No committee members yet')
  })

  it('shows an error state when the fetch fails', async () => {
    mockFetchCommittee.mockRejectedValue(new Error('network error'))

    const wrapper = mount(CommitteeView)
    await flushPromises()

    expect(wrapper.text()).toContain("Couldn't load the committee")
  })

  it('shows a Draft pill only on members the API marks as unpublished (admin preview)', async () => {
    mockFetchCommittee.mockResolvedValue({
      items: [
        { id: 1, name: 'Live One', role: 'President', portrait_url: null, address: null, email: null, phone: null, member_since: null, quote: null, published: true },
        { id: 2, name: 'Hidden One', role: 'Treasurer', portrait_url: null, address: null, email: null, phone: null, member_since: null, quote: null, published: false },
      ],
    })
    const wrapper = mount(CommitteeView)
    await flushPromises()

    expect(wrapper.findAll('.draft-pill')).toHaveLength(1)
    expect(wrapper.findAll('article')[1].find('.draft-pill').exists()).toBe(true)
  })
})
