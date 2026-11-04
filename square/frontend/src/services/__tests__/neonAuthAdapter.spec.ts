// Tests for neonAuthAdapter (4 cases), e.g. normalizeNeonSession; returns null for a null session; maps a Better Auth session/user into the Supabase-shaped MiniSession.
import { describe, expect, it } from 'vitest'
import { normalizeNeonSession } from '../neonAuthAdapter'

describe('normalizeNeonSession', () => {
  it('returns null for a null session', () => {
    expect(normalizeNeonSession(null, 'a-jwt-token')).toBeNull()
  })

  it('maps a Better Auth session/user into the Supabase-shaped MiniSession', () => {
    const result = normalizeNeonSession(
      {
        user: {
          id: 'user-1',
          email: 'a@b.com',
          name: 'Ada Lovelace',
          image: 'https://example.com/avatar.png',
        },
      },
      'a-jwt-token',
    )

    expect(result).toEqual({
      access_token: 'a-jwt-token',
      user: {
        id: 'user-1',
        email: 'a@b.com',
        user_metadata: {
          avatar_url: 'https://example.com/avatar.png',
          picture: 'https://example.com/avatar.png',
          full_name: 'Ada Lovelace',
          name: 'Ada Lovelace',
        },
      },
    })
  })

  it('maps a user with no name/image to undefined metadata fields, not throwing', () => {
    const result = normalizeNeonSession(
      { user: { id: 'user-2', email: 'c@d.com', name: null, image: null } },
      'a-jwt-token',
    )

    expect(result?.user.user_metadata).toEqual({
      avatar_url: undefined,
      picture: undefined,
      full_name: undefined,
      name: undefined,
    })
  })
})
