// Tests for GateScreen (3 cases): the passcode screen of a private deploy (W26-R20) sends the passcode, reloads on success, and says what went wrong otherwise.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const enter = vi.hoisted(() => vi.fn())
vi.mock('../../services/gate', () => ({ gateEnter: enter }))
import GateScreen from '../GateScreen.vue'

describe('GateScreen', () => {
  const reload = vi.fn()
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(window, 'location', { value: { ...window.location, reload }, writable: true })
  })

  it('keeps Continue off until something is typed, then sends the passcode and reloads when it is right', async () => {
    enter.mockResolvedValue('ok')
    const w = mount(GateScreen)
    expect(w.find('.gate-button').attributes('disabled')).toBeDefined()
    await w.find('.gate-input').setValue('the right passcode 123')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(enter).toHaveBeenCalledWith('the right passcode 123')
    expect(reload).toHaveBeenCalled()
  })

  it('says the passcode is wrong and does not reload', async () => {
    enter.mockResolvedValue('wrong')
    const w = mount(GateScreen)
    await w.find('.gate-input').setValue('nope nope nope nope')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.find('[role="alert"]').text()).toContain('not the passcode')
    expect(reload).not.toHaveBeenCalled()
  })

  it('says when there were too many tries and when the server did not answer', async () => {
    const w = mount(GateScreen)
    await w.find('.gate-input').setValue('some passcode here 99')
    enter.mockResolvedValue('limited')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.find('[role="alert"]').text()).toContain('Too many tries')
    enter.mockResolvedValue('error')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.find('[role="alert"]').text()).toContain('did not answer')
  })
})
