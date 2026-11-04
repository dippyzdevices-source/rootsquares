// Tests for useToast (5 cases), e.g. useToast; adds a toast with the requested variant and message; auto-dismisses a toast after the default duration.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useToast } from '../useToast'

describe('useToast', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    const { toasts, dismiss } = useToast()
    while (toasts.length) {
      dismiss(toasts[0].id)
    }
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('adds a toast with the requested variant and message', () => {
    const { success, toasts } = useToast()

    success('Membership renewed')

    expect(toasts).toHaveLength(1)
    expect(toasts[0].message).toBe('Membership renewed')
    expect(toasts[0].variant).toBe('success')
  })

  it('auto-dismisses a toast after the default duration', () => {
    const { error, toasts } = useToast()

    error('Payment failed')
    expect(toasts).toHaveLength(1)

    vi.advanceTimersByTime(4000)

    expect(toasts).toHaveLength(0)
  })

  it('does not dismiss before the requested duration has elapsed', () => {
    const { info, toasts } = useToast()

    info('Still processing')
    vi.advanceTimersByTime(3999)

    expect(toasts).toHaveLength(1)
  })

  it('dismiss removes only the targeted toast', () => {
    const { info, toasts, dismiss } = useToast()

    info('One')
    info('Two')
    const [first] = toasts

    dismiss(first.id)

    expect(toasts).toHaveLength(1)
    expect(toasts[0].message).toBe('Two')
  })
})
