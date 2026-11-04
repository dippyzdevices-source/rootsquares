/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Origin of the platform API, default http://localhost:5001; the staff API lives under /api/admin/v1 (must be listed in ADMIN_ORIGINS on the server side for this application's origin). */
  readonly VITE_ADMIN_API_BASE_URL?: string
}
