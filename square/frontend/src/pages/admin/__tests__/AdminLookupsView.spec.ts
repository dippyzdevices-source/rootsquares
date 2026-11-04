// Tests for AdminLookupsView (7 cases), e.g. AdminLookupsView; lists values of the first list with their status; hides an active value via PATCH is_active=false.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const mockLists = vi.fn()
const mockRows = vi.fn()
const mockCreate = vi.fn()
const mockUpdate = vi.fn()
const mockReorder = vi.fn()

vi.mock('../../../services/lookupsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/lookupsApi')>('../../../services/lookupsApi')
  return {
    ...actual,
    fetchLookupLists: (...a: unknown[]) => mockLists(...a),
    fetchAdminLookup: (...a: unknown[]) => mockRows(...a),
    createLookupValue: (...a: unknown[]) => mockCreate(...a),
    updateLookupValue: (...a: unknown[]) => mockUpdate(...a),
    reorderLookupValues: (...a: unknown[]) => mockReorder(...a),
  }
})

import AdminLookupsView from '../AdminLookupsView.vue'

const row = (id: number, value: string, label: string, active = true) => ({
  id, list_key: 'expense_category', value, label, sort_order: id, is_active: active, usage_count: id === 1 ? 3 : 0,
})

describe('AdminLookupsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockLists.mockResolvedValue([
      { key: 'event_type', title: 'Event types', description: 'Types.', group: 'Content', value_count: 4 },
      { key: 'expense_category', title: 'Expense categories', description: 'Desc.', group: 'Finance', value_count: 11 },
    ])
    mockRows.mockResolvedValue([row(1, 'venue', 'Venue'), row(2, 'food', 'Food', false)])
    mockUpdate.mockResolvedValue({})
    mockReorder.mockResolvedValue(undefined)
  })

  const mountView = () => mount(AdminLookupsView, { global: { stubs: { SettingsSectionNav: true, RouterLink: true } } })

  it('lists values of the first list with their status', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(mockRows).toHaveBeenCalledWith('event_type')
    expect(wrapper.text()).toContain('Venue')
    expect(wrapper.text()).toContain('Hidden')
  })

  it('hides an active value via PATCH is_active=false', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.find('button[aria-label="Hide Venue"], [aria-label="Hide Venue"]').trigger('click')
    expect(mockUpdate).toHaveBeenCalledWith('event_type', 1, { is_active: false })
  })

  it('always shows delete, disabled with the reason when the value is used or built in', async () => {
    const wrapper = mountView()
    await flushPromises()
    const venue = wrapper.find('[aria-label="Delete Venue"]')
    expect(venue.exists()).toBe(true)
    expect(venue.attributes('disabled')).toBeDefined()
    expect(venue.element.closest('.lists-delete')?.getAttribute('title')).toContain('Used by 3 records')
    const food = wrapper.find('[aria-label="Delete Food"]')
    expect(food.attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[aria-label="Hide Venue"]').attributes('disabled')).toBeUndefined()
  })

  it('groups the lists in a side index, switches list on click and filters by search', async () => {
    const wrapper = mountView()
    await flushPromises()
    const rail = wrapper.find('.lists-rail')
    expect(rail.text()).toContain('Content')
    expect(rail.text()).toContain('Finance')
    expect(wrapper.find('.lists-item-on').text()).toContain('Event types')

    const expense = wrapper.findAll('.lists-item').find((b) => b.text().includes('Expense categories'))!
    await expense.trigger('click')
    await flushPromises()
    expect(mockRows).toHaveBeenLastCalledWith('expense_category')
    expect(wrapper.find('h2').text()).toBe('Expense categories')

    await rail.find('input').setValue('event')
    expect(wrapper.findAll('.lists-item').map((b) => b.text())).toEqual([expect.stringContaining('Event types')])
  })

  it('reorders in place with one save request when a handle gets the down arrow key', async () => {
    const wrapper = mountView()
    await flushPromises()
    mockRows.mockClear()

    await wrapper.findAll('.lists-handle')[0].trigger('keydown', { key: 'ArrowDown' })
    await flushPromises()

    expect(mockReorder).toHaveBeenCalledWith('event_type', [2, 1])
    expect(wrapper.findAll('tbody tr')[0].text()).toContain('Food')
    expect(mockRows).not.toHaveBeenCalled() // no reload, so the table does not flash
  })

  it('puts the old order back when saving the new one fails', async () => {
    mockReorder.mockRejectedValue(new Error('boom'))
    const wrapper = mountView()
    await flushPromises()

    await wrapper.findAll('.lists-handle')[0].trigger('keydown', { key: 'ArrowDown' })
    await flushPromises()

    expect(wrapper.findAll('tbody tr')[0].text()).toContain('Venue')
  })
})
