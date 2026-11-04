// Tests for AccountingExpenseModal (7 cases), e.g. AccountingExpenseModal; creates a new expense; pre-fills the form with an existing expense for editing.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { chooseOption } from '../../../test-utils/baseSelect'
import { mount, flushPromises, DOMWrapper, type VueWrapper } from '@vue/test-utils'

const mockCreateExpense = vi.fn()
const mockUpdateExpense = vi.fn()
const mockUploadExpenseReceipt = vi.fn()
const mockDeleteExpenseReceipt = vi.fn()
const mockCameraStart = vi.fn().mockResolvedValue(undefined)
const mockCameraStop = vi.fn()
const mockCameraCapture = vi.fn()

vi.mock('../../../services/lookupsApi', () => ({
  fetchLookup: vi.fn().mockResolvedValue([
    { value: 'venue', label: 'Venue' },
    { value: 'food', label: 'Food' },
    { value: 'decoration', label: 'Decoration' },
  ]),
}))

vi.mock('../../../services/adminAccountingApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminAccountingApi')>(
    '../../../services/adminAccountingApi',
  )
  return {
    ...actual,
    createExpense: (...args: unknown[]) => mockCreateExpense(...args),
    updateExpense: (...args: unknown[]) => mockUpdateExpense(...args),
    uploadExpenseReceipt: (...args: unknown[]) => mockUploadExpenseReceipt(...args),
    deleteExpenseReceipt: (...args: unknown[]) => mockDeleteExpenseReceipt(...args),
  }
})

vi.mock('../../../utils/cameraCapture', () => ({
  createCameraCapture: vi.fn(() => ({
    start: mockCameraStart,
    stop: mockCameraStop,
    capture: mockCameraCapture,
    listCameras: vi.fn().mockResolvedValue([]),
    setCamera: vi.fn().mockResolvedValue(undefined),
  })),
}))

import AccountingExpenseModal from '../AccountingExpenseModal.vue'
import type { Expense } from '../../../services/adminAccountingApi'

let currentWrapper: VueWrapper | null = null

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  currentWrapper?.unmount()
  currentWrapper = null
})

// Mounts closed and then opens via a prop change, mirroring how the real dashboard toggles
// `showExpenseModal` — this is what makes the modal's own open-transition watcher (which
// resets the form) actually fire, the same way it would in real usage.
async function mountOpen(expense: Expense | null) {
  const wrapper = mount(AccountingExpenseModal, {
    props: { modelValue: false, eventId: 5, expense },
  })
  currentWrapper = wrapper
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  return wrapper
}

describe('AccountingExpenseModal', () => {
  it('creates a new expense', async () => {
    mockCreateExpense.mockResolvedValue({
      id: 1, event_id: 5, date: '2026-10-01', description: 'Hall rental', category: 'venue',
      amount: 500000, vendor: null, notes: null, receipt_key: null, receipt_url: null,
      created_by: null, created_at: '', updated_at: '',
    })

    const wrapper = await mountOpen(null)

    const body = new DOMWrapper(document.body)
    await body.find('input[type="date"]').setValue('2026-10-01')
    const textInputs = body.findAll('input[type="text"]')
    await textInputs[0].setValue('Hall rental')
    await chooseOption(body, 'venue')
    await body.find('input[type="number"]').setValue('5000')

    const saveButton = body.findAll('button').find((b) => b.text().includes('Save'))
    await saveButton!.trigger('click')
    await flushPromises()

    expect(mockCreateExpense).toHaveBeenCalledWith(5, expect.objectContaining({
      date: '2026-10-01',
      description: 'Hall rental',
      category: 'venue',
      amount: 500000,
    }))
    expect(wrapper.emitted('saved')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
  })

  it('pre-fills the form with an existing expense for editing', async () => {
    const expense = {
      id: 2, event_id: 5, date: '2026-09-15', description: 'Flowers', category: 'decoration',
      amount: 25000, vendor: 'Oslo Blomster', notes: null, receipt_key: null, receipt_url: null,
      created_by: null, created_at: '', updated_at: '',
    }

    await mountOpen(expense)

    const body = new DOMWrapper(document.body)
    expect((body.find('input[type="number"]').element as HTMLInputElement).value).toBe('250')
    expect(body.text()).toContain('Edit expense')
  })

  it('shows validation errors from the API', async () => {
    const { ValidationError } = await vi.importActual<typeof import('../../../services/adminAccountingApi')>(
      '../../../services/adminAccountingApi',
    )
    mockCreateExpense.mockRejectedValue(new ValidationError({ description: 'This field is required.' }))

    await mountOpen(null)

    const body = new DOMWrapper(document.body)
    const saveButton = body.findAll('button').find((b) => b.text().includes('Save'))
    await saveButton!.trigger('click')
    await flushPromises()

    expect(body.text()).toContain('This field is required.')
  })

  it('uploads a selected receipt file after creating the expense', async () => {
    mockCreateExpense.mockResolvedValue({
      id: 3, event_id: 5, date: '2026-10-01', description: 'Hall rental', category: 'venue',
      amount: 500000, vendor: null, notes: null, receipt_key: null, receipt_url: null,
      created_by: null, created_at: '', updated_at: '',
    })
    mockUploadExpenseReceipt.mockResolvedValue({
      id: 3, event_id: 5, date: '2026-10-01', description: 'Hall rental', category: 'venue',
      amount: 500000, vendor: null, notes: null, receipt_key: 'receipts/5/3-abc-receipt.png',
      receipt_url: 'https://example.com/receipt.png', created_by: null, created_at: '', updated_at: '',
    })

    const wrapper = await mountOpen(null)
    const body = new DOMWrapper(document.body)

    await body.find('input[type="date"]').setValue('2026-10-01')
    const textInputs = body.findAll('input[type="text"]')
    await textInputs[0].setValue('Hall rental')
    await chooseOption(body, 'venue')
    await body.find('input[type="number"]').setValue('5000')

    const fileInput = body.find('input[type="file"]')
    const file = new File(['receipt-bytes'], 'receipt.png', { type: 'image/png' })
    Object.defineProperty(fileInput.element, 'files', { value: [file] })
    await fileInput.trigger('change')

    const saveButton = body.findAll('button').find((b) => b.text().includes('Save'))
    await saveButton!.trigger('click')
    await flushPromises()

    expect(mockUploadExpenseReceipt).toHaveBeenCalledWith(3, file)
    expect(wrapper.emitted('saved')?.[0]).toEqual([expect.objectContaining({ receipt_url: 'https://example.com/receipt.png' })])
  })

  it('shows a link to an existing receipt when editing, and can remove it', async () => {
    const expense = {
      id: 4, event_id: 5, date: '2026-09-15', description: 'Flowers', category: 'decoration',
      amount: 25000, vendor: 'Oslo Blomster', notes: null, receipt_key: 'receipts/5/4-abc.png',
      receipt_url: 'https://example.com/receipt.png', created_by: null, created_at: '', updated_at: '',
    }
    mockDeleteExpenseReceipt.mockResolvedValue({ ...expense, receipt_key: null, receipt_url: null })

    await mountOpen(expense)
    const body = new DOMWrapper(document.body)

    const viewButton = body.findAll('button').find((b) => b.text().includes('View current receipt'))
    expect(viewButton).toBeTruthy()
    await viewButton!.trigger('click')
    expect(body.find('img[src="https://example.com/receipt.png"]').exists()).toBe(true)

    const removeButton = body.findAll('button').find((b) => b.text().includes('Remove'))
    await removeButton!.trigger('click')
    await flushPromises()

    expect(mockDeleteExpenseReceipt).toHaveBeenCalledWith(4)
    expect(body.findAll('button').find((b) => b.text().includes('View current receipt'))).toBeUndefined()
  })

  it('offers a live camera capture alongside choosing a saved file', async () => {
    mockCameraCapture.mockResolvedValue(new File(['photo-bytes'], 'captured.jpg', { type: 'image/jpeg' }))

    await mountOpen(null)
    const body = new DOMWrapper(document.body)

    expect(body.findAll('input[type="file"]')).toHaveLength(1) // the browse-only input

    const takePhotoButton = body.findAll('button').find((b) => b.text().includes('Take photo'))
    await takePhotoButton!.trigger('click')
    await flushPromises()

    expect(mockCameraStart).toHaveBeenCalledTimes(1)

    const captureButton = body.findAll('button').find((b) => b.text() === 'Capture')
    await captureButton!.trigger('click')
    await flushPromises()

    expect(mockCameraCapture).toHaveBeenCalledTimes(1)
    expect(mockCameraStop).toHaveBeenCalled() // camera modal closes itself after a capture
    expect(body.text()).toContain('captured.jpg')
  })
})
