/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "true" = in-browser mock of the platform API; default is the real API */
  readonly VITE_USE_MOCK?: string
  /** Platform API origin, default http://localhost:5001 */
  readonly VITE_API_BASE_URL?: string
  /** Host names of the platform itself, comma separated (default localhost,127.0.0.1). Any other host name is shown as a square. */
  readonly VITE_PLATFORM_HOSTS?: string
  /** Identity provider for sign-in (ADR 028): "supabase" (local/test) or "neon" (production). Empty = the platform's own cookie login only. */
  readonly VITE_AUTH_PROVIDER?: string
  /** The provider's base URL: Supabase project URL, or the Neon Auth URL */
  readonly VITE_AUTH_URL?: string
  /** Supabase publishable (anon) key. Supabase only. */
  readonly VITE_AUTH_PUBLIC_KEY?: string
}
