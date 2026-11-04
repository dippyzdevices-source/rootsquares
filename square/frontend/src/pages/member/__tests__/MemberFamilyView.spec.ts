// Tests for MemberFamilyView (7 cases), e.g. MemberFamilyView; shows existing family members; shows an empty state when there are no family members yet.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { chooseOption } from '../../../test-utils/baseSelect'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchMyMember = vi.fn()
const mockCreateMyFamilyMember = vi.fn()
const mockUpdateMyFamilyMember = vi.fn()
const mockDeleteMyFamilyMember = vi.fn()

vi.mock('../../../services/lookupsApi', () => ({
  fetchLookup: vi.fn().mockResolvedValue([
    { value: 'spouse', label: 'Spouse' },
    { value: 'child', label: 'Child' },
    { value: 'parent', label: 'Parent' },
    { value: 'other', label: 'Other' },
  ]),
}))

vi.mock('../../../services/memberApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/memberApi')>(
    '../../../services/memberApi',
  )
  return {
    ...actual,
    fetchMyMember: (...args: unknown[]) => mockFetchMyMember(...args),
    createMyFamilyMember: (...args: unknown[]) => mockCreateMyFamilyMember(...args),
    updateMyFamilyMember: (...args: unknown[]) => mockUpdateMyFamilyMember(...args),
    deleteMyFamilyMember: (...args: unknown[]) => mockDeleteMyFamilyMember(...args),
  }
})

import MemberFamilyView from '../MemberFamilyView.vue'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('MemberFamilyView', () => {
  it('shows existing family members', async () => {
    mockFetchMyMember.mockResolvedValue({
      id: 1,
      name: 'Priya Das',
      address: null,
      family_info: null,
      family_members: [{ id: 1, name: 'Anita', relationship_type: 'spouse', age: 34, sort_order: 0 }],
    })

    const wrapper = mount(MemberFamilyView)
    await flushPromises()

    expect(wrapper.text()).toContain('Anita')
    expect(wrapper.text()).toContain('Spouse')
    expect(wrapper.text()).toContain('34')
  })

  it('shows an empty state when there are no family members yet', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })

    const wrapper = mount(MemberFamilyView)
    await flushPromises()

    expect(wrapper.text()).toContain('No family members added yet.')
  })

  it('adds a family member via the inline form', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })
    mockCreateMyFamilyMember.mockResolvedValue({ id: 2, name: 'Rohan', relationship_type: 'child', age: 8, sort_order: 1 })

    const wrapper = mount(MemberFamilyView)
    await flushPromises()

    await wrapper.find('button.add-family-member').trigger('click')
    await wrapper.find('input').setValue('Rohan')
    await chooseOption(wrapper, 'child')
    await wrapper.find('input[type="number"]').setValue('8')
    await wrapper.find('button.save-family-member').trigger('click')
    await flushPromises()

    expect(mockCreateMyFamilyMember).toHaveBeenCalledWith({
      name: 'Rohan',
      relationship_type: 'child',
      age: 8,
    })
  })

  it('removes a family member', async () => {
    mockFetchMyMember.mockResolvedValue({
      id: 1,
      name: 'Priya Das',
      address: null,
      family_info: null,
      family_members: [{ id: 1, name: 'Anita', relationship_type: 'spouse', age: 34, sort_order: 0 }],
    })
    mockDeleteMyFamilyMember.mockResolvedValue(undefined)

    const wrapper = mount(MemberFamilyView)
    await flushPromises()

    await wrapper.find('button[aria-label="Remove Anita"]').trigger('click')
    await flushPromises()

    expect(mockDeleteMyFamilyMember).toHaveBeenCalledWith(1)
    expect(wrapper.text()).not.toContain('Anita')
  })

  it('shows a validation error from the API', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })
    const { ValidationError } = await vi.importActual<typeof import('../../../services/memberApi')>(
      '../../../services/memberApi',
    )
    mockCreateMyFamilyMember.mockRejectedValue(new ValidationError({ name: 'This field is required.' }))

    const wrapper = mount(MemberFamilyView)
    await flushPromises()

    await wrapper.find('button.add-family-member').trigger('click')
    await wrapper.find('button.save-family-member').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('This field is required.')
  })

  it('shows an error state when the fetch fails', async () => {
    mockFetchMyMember.mockRejectedValue(new Error('network error'))

    const wrapper = mount(MemberFamilyView)
    await flushPromises()

    expect(wrapper.text()).toContain("Couldn't load")
  })
})
