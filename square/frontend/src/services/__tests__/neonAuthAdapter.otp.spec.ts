// Tests for neonAuthAdapter.otp (5 cases), e.g. neon adapter email OTP; verifyOtp maps to emailOtp.verifyEmail with the code as `otp`; verifyOtp normalizes a Better Auth error into an Error.
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockClient = vi.hoisted(() => ({
  emailOtp: { verifyEmail: vi.fn(), sendVerificationOtp: vi.fn() },
}))

vi.mock('@neondatabase/auth', () => ({ createAuthClient: () => mockClient }))

import { createNeonAuthAdapter } from '../neonAuthAdapter'

beforeEach(() => vi.clearAllMocks())

describe('neon adapter email OTP', () => {
  it('verifyOtp maps to emailOtp.verifyEmail with the code as `otp`', async () => {
    mockClient.emailOtp.verifyEmail.mockResolvedValue({ data: {}, error: null })
    const adapter = createNeonAuthAdapter('https://neon.example/auth')

    const result = await adapter.auth.verifyOtp({ email: 'a@b.com', token: '123456', type: 'signup' })

    expect(mockClient.emailOtp.verifyEmail).toHaveBeenCalledWith({ email: 'a@b.com', otp: '123456' })
    expect(result).toEqual({ error: null })
  })

  it('verifyOtp normalizes a Better Auth error into an Error', async () => {
    mockClient.emailOtp.verifyEmail.mockResolvedValue({ data: null, error: { message: 'Invalid OTP' } })
    const adapter = createNeonAuthAdapter('https://neon.example/auth')

    const result = await adapter.auth.verifyOtp({ email: 'a@b.com', token: '000000', type: 'signup' })

    expect(result.error).toBeInstanceOf(Error)
    expect(result.error?.message).toBe('Invalid OTP')
  })

  it("resend maps to emailOtp.sendVerificationOtp with type 'email-verification'", async () => {
    mockClient.emailOtp.sendVerificationOtp.mockResolvedValue({ data: {}, error: null })
    const adapter = createNeonAuthAdapter('https://neon.example/auth')

    const result = await adapter.auth.resend({ type: 'signup', email: 'a@b.com' })

    expect(mockClient.emailOtp.sendVerificationOtp).toHaveBeenCalledWith({
      email: 'a@b.com',
      type: 'email-verification',
    })
    expect(result).toEqual({ error: null })
  })

  it('resend normalizes an error', async () => {
    mockClient.emailOtp.sendVerificationOtp.mockResolvedValue({ data: null, error: { message: 'Too many requests' } })
    const adapter = createNeonAuthAdapter('https://neon.example/auth')

    const result = await adapter.auth.resend({ type: 'signup', email: 'a@b.com' })

    expect(result.error?.message).toBe('Too many requests')
  })
})
