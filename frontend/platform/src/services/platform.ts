// Platform API (accounts, squares). Real API by default; VITE_USE_MOCK=true switches to an in-browser mock with the same interface. Everything outside the
// platform (square console, tenant site) stays mock data in services/api.ts. The types live in platformTypes.ts; the admin console has its own client (ADR 083).
import { platformApi } from './platformApi'
import { platformMock } from './platformMock'
import type { PlatformApi } from '@/services/platformTypes'

export * from './platformTypes'
export * from '@rootsquares/ui/types/platformTypes'

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
export const platform: PlatformApi = USE_MOCK ? platformMock : platformApi
