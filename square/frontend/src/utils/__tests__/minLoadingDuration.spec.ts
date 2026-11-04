// Tests for minLoadingDuration (2 cases), e.g. ensureMinLoadingDuration; resolves immediately under the test environment (no real delay in test.
import { describe, it, expect } from 'vitest'
import { ensureMinLoadingDuration } from '../minLoadingDuration'

describe('ensureMinLoadingDuration', () => {
  it('resolves immediately under the test environment (no real delay in test runs)', async () => {
    const startedAt = Date.now()
    await ensureMinLoadingDuration(startedAt, 5000)
    expect(Date.now() - startedAt).toBeLessThan(100)
  })
})
