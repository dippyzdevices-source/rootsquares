// How a brand-new email/password account confirms its address, per identity provider.
// Supabase emails a confirmation LINK and needs nothing from the app; Neon Auth is configured for
// a 6-digit CODE the user must type into RegisterView.
//
// Follows supabaseClient.ts's provider choice (VITE_AUTH_PROVIDER) — Neon only when it is
// exactly 'neon'. It deliberately does NOT throw on a missing/unknown provider (supabaseClient.ts
// is the single fail-loud place); it falls back to 'link' so a misconfigured build can never show
// a code step that has no email behind it.
// Kept in its own module (not exported from supabaseClient.ts) so specs that mock
// supabaseClient wholesale don't lose it.
export type EmailVerificationMode = 'code' | 'link'

export const emailVerificationMode: EmailVerificationMode =
  (import.meta.env.VITE_AUTH_PROVIDER as string) === 'neon' ? 'code' : 'link'
