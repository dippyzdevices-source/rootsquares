// Skipped under Vitest — a real delay here would make every existing `await flushPromises()`
// test either flake or need fake timers, for a purely cosmetic minimum-visible-time guarantee.
const isTestEnv = import.meta.env.MODE === 'test'

// Ensures a loading state stays visible for at least `minMs` from when it started, so a
// near-instant fetch doesn't flash the themed spinner content too fast to register.
export async function ensureMinLoadingDuration(startedAt: number, minMs = 1000): Promise<void> {
  if (isTestEnv) return
  const remaining = minMs - (Date.now() - startedAt)
  if (remaining > 0) {
    await new Promise((resolve) => setTimeout(resolve, remaining))
  }
}
