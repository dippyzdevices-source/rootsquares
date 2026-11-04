// Despite the filename, this module is provider-abstracted: it exports a Neon Auth
// (Better Auth) adapter or the real Supabase client, selected purely by VITE_AUTH_PROVIDER
// ('neon' | 'supabase') with VITE_AUTH_URL as that provider's base URL. The filename/export
// name are kept as-is deliberately — ~26 service files plus stores/auth.ts already import
// `supabase` and call `supabase.auth.*` directly; renaming this module would mean touching every
// one of them for no functional benefit. See
// docs/superpowers/specs/2026-09-23-dual-provider-auth-design.md.
//
// There is deliberately no default and no VITE_APP_ENV coupling: a wrong guess would sign users
// in against the wrong identity provider, so a missing/unknown provider or an empty URL throws
// at load instead. Mirrors backend/app/config.py's AUTH_PROVIDER/AUTH_URL.
import { createClient } from '@supabase/supabase-js'
import { createNeonAuthAdapter, type MiniAuthClient } from './neonAuthAdapter'

// rootsquares change (W6-R27, W6-R36): one server serves many squares, each with its OWN sign-in project. The square's project comes from
// services/squareConfig.ts (asked once). The VITE_AUTH_* values are only the fallback for a single-tenant server and for the test suite.
import { squareAuth } from './squareConfig'
// A rootsquares support session (W23-R66) signs in with the platform's token instead of the square's own sign-in: see supportSession.ts.
import { withSupport } from './supportSession'

const provider = (squareAuth?.provider || import.meta.env.VITE_AUTH_PROVIDER) as string | undefined
const authUrl = (squareAuth?.url || import.meta.env.VITE_AUTH_URL) as string | undefined
const publicKey = (squareAuth?.public_key || import.meta.env.VITE_AUTH_PUBLIC_KEY) as string

if (provider !== 'supabase' && provider !== 'neon') {
  throw new Error(
    `VITE_AUTH_PROVIDER must be "supabase" or "neon" (got ${JSON.stringify(provider)}). ` +
      'Set it in square/frontend/.env.local — see square/frontend/.env.example.',
  )
}
if (!authUrl) {
  throw new Error(
    'VITE_AUTH_URL must be set to the auth provider\'s base URL. Set it in square/frontend/.env.local — see square/frontend/.env.example.',
  )
}

export const supabase: MiniAuthClient = withSupport(
  provider === 'neon' ? createNeonAuthAdapter(authUrl) : (createClient(authUrl, publicKey) as unknown as MiniAuthClient),
)
