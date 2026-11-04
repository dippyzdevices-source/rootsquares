// Tests for AdminMembershipTypesView (6 cases), e.g. AdminMembershipTypesView; lists membership types with price and status; creates a new membership type via the modal.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockFetchAdminMembershipTypes = vi.fn()
const mockCreateAdminMembershipType = vi.fn()
const mockUpdateAdminMembershipType = vi.fn()

vi.mock('../../../services/adminMembershipTypesApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminMembershipTypesApi')>(
    '../../../services/adminMembershipTypesApi',
  )
  return {
    ...actual,
    fetchAdminMembershipTypes: (...args: unknown[]) => mockFetchAdminMembershipTypes(...args),
    createAdminMembershipType: (...args: unknown[]) => mockCreateAdminMembershipType(...args),
    updateAdminMembershipType: (...args: unknown[]) => mockUpdateAdminMembershipType(...args),
  }
})

import AdminMembershipTypesView from '../AdminMembershipTypesView.vue'

const stubs = { RouterLink: true }

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAdminMembershipTypes.mockResolvedValue({
    items: [
      {
        name: 'individual',
        price: 500,
        billing_frequency: 'yearly',
        contact_for_price: false,
        is_active: true,
        sort_order: 0,
      },
      {
        name: 'retired',
        price: 0,
        billing_frequency: 'yearly',
        contact_for_price: false,
        is_active: false,
        sort_order: 1,
      },
    ],
  })
})

describe('AdminMembershipTypesView', () => {
  it('lists membership types with price and status', async () => {
    const wrapper = mount(AdminMembershipTypesView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Individual')
    expect(wrapper.text()).toContain('500 kr')
    expect(wrapper.text()).toContain('Active')
    expect(wrapper.text()).toContain('Inactive')
  })

  it('creates a new membership type via the modal', async () => {
    mockCreateAdminMembershipType.mockResolvedValue({
      name: 'student',
      price: 250,
      is_active: true,
      sort_order: 0,
    })

    const wrapper = mount(AdminMembershipTypesView, { global: { stubs } })
    await flushPromises()

    await wrapper.findAll('button').find((b) => b.text() === 'Add type')!.trigger('click')

    const body = new DOMWrapper(document.body)
    const inputs = body.findAll('input')
    await inputs[0].setValue('student')
    await inputs[1].setValue('250')
    await body.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()

    expect(mockCreateAdminMembershipType).toHaveBeenCalledWith({
      name: 'student',
      price: 250,
      billing_frequency: 'yearly',
      contact_for_price: false,
      description: '',
      is_active: true,
      sort_order: 0,
    })

    wrapper.unmount()
  })

  it('edits an existing membership type without allowing a name change', async () => {
    mockUpdateAdminMembershipType.mockResolvedValue({
      name: 'individual',
      price: 750,
      billing_frequency: 'yearly',
      contact_for_price: false,
      description: '',
      is_active: true,
      sort_order: 0,
    })

    const wrapper = mount(AdminMembershipTypesView, { global: { stubs } })
    await flushPromises()

    await wrapper.findAll('button').find((b) => b.attributes('aria-label')?.startsWith('Edit '))!.trigger('click')

    const body = new DOMWrapper(document.body)
    expect((body.find('input[type="text"]').element as HTMLInputElement).disabled).toBe(true)
    await body.find('input[type="number"]').setValue('750')
    await body.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()

    expect(mockUpdateAdminMembershipType).toHaveBeenCalledWith('individual', {
      price: 750,
      billing_frequency: 'yearly',
      contact_for_price: false,
      description: '',
      is_active: true,
      sort_order: 0,
    })

    wrapper.unmount()
  })

  it('switches a type to "contact for pricing" via the checkbox', async () => {
    mockUpdateAdminMembershipType.mockResolvedValue({
      name: 'individual',
      price: 500,
      billing_frequency: 'yearly',
      contact_for_price: true,
      is_active: true,
      sort_order: 0,
    })

    const wrapper = mount(AdminMembershipTypesView, { global: { stubs } })
    await flushPromises()

    await wrapper.findAll('button').find((b) => b.attributes('aria-label')?.startsWith('Edit '))!.trigger('click')

    const body = new DOMWrapper(document.body)
    const checkboxes = body.findAll('input[type="checkbox"]')
    await checkboxes[0].setValue(true) // "Contact for pricing" is the first checkbox
    await body.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()

    expect(mockUpdateAdminMembershipType).toHaveBeenCalledWith(
      'individual',
      expect.objectContaining({ contact_for_price: true }),
    )

    wrapper.unmount()
  })

  it('shows "Contact us for pricing" in the list for a contact-for-price type', async () => {
    mockFetchAdminMembershipTypes.mockResolvedValue({
      items: [
        {
          name: 'lifetime',
          price: 0,
          billing_frequency: 'yearly',
          contact_for_price: true,
          is_active: true,
          sort_order: 0,
        },
      ],
    })

    const wrapper = mount(AdminMembershipTypesView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Contact us for pricing')
  })
})
