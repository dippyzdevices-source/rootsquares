// Tests for EventRepeatCardLocked (2 cases), e.g. EventRepeatCard when the package has no repeating events; shows the card with a disabled button and the package line.
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// A square whose package does not include repeating events (W14-R25): the card stays, locked, with the package named.
vi.mock('../../services/features', () => ({ featureEnabled: () => false, GROVE_NOTE: 'Included in the Grove package.' }))
vi.mock('../../services/eventSeriesApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/eventSeriesApi')>()),
  fetchEventSeries: () => Promise.resolve({ series: null }),
}))

import EventRepeatCard from '../EventRepeatCard.vue'

describe('EventRepeatCard when the package has no repeating events', () => {
  it('shows the card with a disabled button and the package line', async () => {
    const wrapper = mount(EventRepeatCard, { props: { eventId: 5 } })
    await flushPromises()
    expect(wrapper.find('.make-repeat').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.feature-locked').text()).toBe('Included in the Grove package.')
  })
})
