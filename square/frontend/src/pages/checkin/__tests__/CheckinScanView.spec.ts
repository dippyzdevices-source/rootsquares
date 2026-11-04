// Tests for CheckinScanView (20 cases), e.g. CheckinScanView; shows the live check-in count, with no event pre-selected; starts the camera scanner against the video element on mount.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { chooseOption } from '../../../test-utils/baseSelect'
import { mount, flushPromises } from '@vue/test-utils'

const mockScanTicket = vi.fn()
const mockFetchCheckinSummary = vi.fn()
const mockStart = vi.fn().mockResolvedValue(undefined)
const mockStop = vi.fn()
const mockPause = vi.fn()
const mockListCameras = vi.fn().mockResolvedValue([])
const mockSetCamera = vi.fn().mockResolvedValue(undefined)

vi.mock('../../../services/checkinApi', () => ({
  scanTicket: (...args: unknown[]) => mockScanTicket(...args),
  fetchCheckinSummary: (...args: unknown[]) => mockFetchCheckinSummary(...args),
}))

vi.mock('../../../utils/qrScanner', () => ({
  createQrScanner: vi.fn(() => ({
    start: mockStart,
    stop: mockStop,
    pause: mockPause,
    listCameras: mockListCameras,
    setCamera: mockSetCamera,
  })),
}))

import CheckinScanView from '../CheckinScanView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchCheckinSummary.mockResolvedValue({ total_tickets: 10, checked_in_count: 3 })
  mockStart.mockResolvedValue(undefined)
  mockListCameras.mockResolvedValue([])
})

afterEach(() => {
  vi.useRealTimers()
})

describe('CheckinScanView', () => {
  it('shows the live check-in count, with no event pre-selected', async () => {
    const wrapper = mount(CheckinScanView)
    await flushPromises()

    expect(mockFetchCheckinSummary).toHaveBeenCalledWith()
    expect(wrapper.text()).toContain('3 / 10 in')
    wrapper.unmount()
  })

  it('starts the camera scanner against the video element on mount', async () => {
    const wrapper = mount(CheckinScanView)
    await flushPromises()

    expect(mockStart).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('submits a manually entered code with no event id and shows a tap-to-dismiss success panel with ticket details', async () => {
    mockScanTicket.mockResolvedValue({
      result: 'valid', customer_name: 'Priya Das', ticket_type: 'Adult',
      event_title: 'Durga Puja 2026',
    })

    const wrapper = mount(CheckinScanView)
    await flushPromises()

    await wrapper.find('input').setValue('abc123')
    await wrapper.find('button.manual-checkin').trigger('click')
    await flushPromises()

    expect(mockScanTicket).toHaveBeenCalledWith('abc123')
    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('Adult')
    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.find('.checkin-result-panel').exists()).toBe(true)
    wrapper.unmount()
  })

  it('ignores a second submission while the first scan is still in flight', async () => {
    let resolveScan!: (value: unknown) => void
    mockScanTicket.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveScan = resolve
        }),
    )

    const wrapper = mount(CheckinScanView)
    await flushPromises()

    await wrapper.find('input').setValue('abc123')
    const button = wrapper.find('button.manual-checkin')

    // Fire two submissions back-to-back before the first scanTicket call resolves —
    // simulates the qr-scanner library's decode callback firing repeatedly per second
    // while the same code stays framed in the camera.
    const firstClick = button.trigger('click')
    const secondClick = button.trigger('click')
    await Promise.all([firstClick, secondClick])

    expect(mockScanTicket).toHaveBeenCalledTimes(1)

    resolveScan({ result: 'valid', customer_name: 'Priya Das', ticket_type: 'Adult' })
    await flushPromises()

    expect(wrapper.text()).toContain('Priya Das')
    wrapper.unmount()
  })

  it('shows an already-used panel with a human-readable check-in date and time, not the raw ISO string', async () => {
    mockScanTicket.mockResolvedValue({
      result: 'already_used', customer_name: 'Priya Das', ticket_type: 'Adult',
      checked_in_at: '2026-10-10T18:00:00+00:00', checked_in_by: 'door@example.com',
    })

    const wrapper = mount(CheckinScanView)
    await flushPromises()
    await wrapper.find('input').setValue('abc123')
    await wrapper.find('button.manual-checkin').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Already checked in')
    expect(wrapper.text()).not.toContain('2026-10-10T18:00:00')
    expect(wrapper.text()).toContain('Oct')
    wrapper.unmount()
  })

  it('shows who scanned an already-used ticket under a muted "Checked in by" label, as an avatar/name row with the email as a caption underneath', async () => {
    mockScanTicket.mockResolvedValue({
      result: 'already_used', customer_name: 'Priya Das', ticket_type: 'Adult',
      checked_in_at: '2026-10-10T18:00:00+00:00', checked_in_by: 'door@example.com',
      checked_in_by_name: 'Door Volunteer',
    })

    const wrapper = mount(CheckinScanView)
    await flushPromises()
    await wrapper.find('input').setValue('abc123')
    await wrapper.find('button.manual-checkin').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Checked in by')
    expect(wrapper.text()).toContain('Door Volunteer')
    expect(wrapper.text()).toContain('door@example.com')
    expect(wrapper.find('.ds-checkin-scanned-by').text()).toContain('DV') // BaseAvatar initials fallback
    wrapper.unmount()
  })

  it('shows a not-assigned panel naming the ticket\'s real event, auto-detected from the scan', async () => {
    mockScanTicket.mockResolvedValue({ result: 'not_assigned', event_title: 'Saraswati Puja 2026' })

    const wrapper = mount(CheckinScanView)
    await flushPromises()
    await wrapper.find('input').setValue('abc123')
    await wrapper.find('button.manual-checkin').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Not your event')
    expect(wrapper.text()).toContain('Saraswati Puja 2026')
    wrapper.unmount()
  })

  it('shows an invalid panel for an unknown code', async () => {
    mockScanTicket.mockResolvedValue({ result: 'invalid' })

    const wrapper = mount(CheckinScanView)
    await flushPromises()
    await wrapper.find('input').setValue('nope')
    await wrapper.find('button.manual-checkin').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Invalid ticket')
    wrapper.unmount()
  })

  it('shows a distinct error panel (not "Invalid ticket") when the scan request itself fails', async () => {
    mockScanTicket.mockRejectedValue(new Error('Scan request failed: 500'))

    const wrapper = mount(CheckinScanView)
    await flushPromises()
    await wrapper.find('input').setValue('abc123')
    await wrapper.find('button.manual-checkin').trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Invalid ticket')
    expect(wrapper.text()).toContain("Couldn't reach the server")
    wrapper.unmount()
  })

  it('dismisses the result panel on tap so scanning can resume', async () => {
    mockScanTicket.mockResolvedValue({ result: 'invalid' })

    const wrapper = mount(CheckinScanView)
    await flushPromises()
    await wrapper.find('input').setValue('nope')
    await wrapper.find('button.manual-checkin').trigger('click')
    await flushPromises()
    expect(wrapper.find('.checkin-result-panel').exists()).toBe(true)

    await wrapper.find('.checkin-result-panel').trigger('click')

    expect(wrapper.find('.checkin-result-panel').exists()).toBe(false)
    wrapper.unmount()
  })

  it('pauses the scanner while a result panel is showing, and resumes it on dismiss', async () => {
    mockScanTicket.mockResolvedValue({ result: 'invalid' })

    const wrapper = mount(CheckinScanView)
    await flushPromises()
    expect(mockStart).toHaveBeenCalledTimes(1) // camera start on mount

    await wrapper.find('input').setValue('abc123')
    await wrapper.find('button.manual-checkin').trigger('click')
    await flushPromises()

    expect(mockPause).toHaveBeenCalledTimes(1)

    await wrapper.find('.checkin-result-panel').trigger('click')

    expect(mockStart).toHaveBeenCalledTimes(2) // resumed by calling start() again
    wrapper.unmount()
  })

  it('pauses the scanner during a valid-scan result and resumes only once the volunteer taps to dismiss', async () => {
    mockScanTicket.mockResolvedValue({ result: 'valid', customer_name: 'Priya Das', ticket_type: 'Adult' })

    const wrapper = mount(CheckinScanView)
    await flushPromises()
    expect(mockStart).toHaveBeenCalledTimes(1) // camera start on mount

    await wrapper.find('input').setValue('abc123')
    await wrapper.find('button.manual-checkin').trigger('click')
    await flushPromises()

    expect(mockPause).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Priya Das')
    expect(mockStart).toHaveBeenCalledTimes(1) // not yet resumed

    await wrapper.find('.checkin-result-panel').trigger('click')

    expect(wrapper.text()).not.toContain('Priya Das')
    expect(mockStart).toHaveBeenCalledTimes(2) // resumed on dismiss
    wrapper.unmount()
  })

  it('shows a pre-event panel with a warning tone and the ticket details when scanned before the event starts', async () => {
    mockScanTicket.mockResolvedValue({
      result: 'pre_event', customer_name: 'Priya Das', ticket_type: 'Adult',
      event_title: 'Durga Puja 2026', event_start_date: '2026-10-15',
    })

    const wrapper = mount(CheckinScanView)
    await flushPromises()
    await wrapper.find('input').setValue('abc123')
    await wrapper.find('button.manual-checkin').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Not yet valid')
    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.find('.ds-checkin-result-tone-warning').exists()).toBe(true)
    wrapper.unmount()
  })

  it('shows a post-event panel with a danger tone and the ticket details when scanned after the event has ended', async () => {
    mockScanTicket.mockResolvedValue({
      result: 'post_event', customer_name: 'Priya Das', ticket_type: 'Adult',
      event_title: 'Durga Puja 2026', event_end_date: '2026-10-16',
    })

    const wrapper = mount(CheckinScanView)
    await flushPromises()
    await wrapper.find('input').setValue('abc123')
    await wrapper.find('button.manual-checkin').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Event has ended')
    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.find('.ds-checkin-result-tone-danger').exists()).toBe(true)
    wrapper.unmount()
  })

  it('does not try to resume the camera on dismiss when it was never available (manual-entry-only mode)', async () => {
    mockStart.mockRejectedValueOnce(new Error('Camera not found'))
    mockScanTicket.mockResolvedValue({ result: 'invalid' })

    const wrapper = mount(CheckinScanView)
    await flushPromises()
    expect(mockStart).toHaveBeenCalledTimes(1) // failed on mount, cameraAvailable stays false

    await wrapper.find('input').setValue('nope')
    await wrapper.find('button.manual-checkin').trigger('click')
    await flushPromises()
    await wrapper.find('.checkin-result-panel').trigger('click')
    await flushPromises()

    // dismissResult must not call start() again — doing so would just re-throw the same
    // camera error as an unhandled rejection, since the camera never came up in the first place.
    expect(mockStart).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('polls the summary endpoint on an interval', async () => {
    vi.useFakeTimers()
    const wrapper = mount(CheckinScanView)
    await flushPromises()
    expect(mockFetchCheckinSummary).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(5000)

    expect(mockFetchCheckinSummary).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('does not show a camera picker when only one camera is available', async () => {
    mockListCameras.mockResolvedValue([{ id: 'cam-1', label: 'Built-in camera' }])

    const wrapper = mount(CheckinScanView)
    await flushPromises()

    expect(wrapper.find('.base-select').exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows a camera picker and lets the user switch cameras when more than one is available', async () => {
    mockListCameras.mockResolvedValue([
      { id: 'cam-1', label: 'Built-in camera' },
      { id: 'cam-2', label: 'External USB webcam' },
    ])

    const wrapper = mount(CheckinScanView)
    await flushPromises()

    expect(wrapper.find('.base-select').exists()).toBe(true)
    await wrapper.find('.base-select-button').trigger('click')
    expect(wrapper.text()).toContain('External USB webcam')

    await chooseOption(wrapper, 'cam-2')
    await flushPromises()

    expect(mockSetCamera).toHaveBeenCalledWith('cam-2')
    wrapper.unmount()
  })

  it('does not show a camera picker when the camera itself is unavailable', async () => {
    mockStart.mockRejectedValueOnce(new Error('Camera not found'))
    mockListCameras.mockResolvedValue([
      { id: 'cam-1', label: 'Built-in camera' },
      { id: 'cam-2', label: 'External USB webcam' },
    ])

    const wrapper = mount(CheckinScanView)
    await flushPromises()

    expect(wrapper.find('.base-select').exists()).toBe(false)
    expect(mockListCameras).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
