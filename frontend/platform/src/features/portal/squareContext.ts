import { inject, provide, type Ref } from 'vue'
import type { PlatformSquare } from '@/services/platform'

// The square of the portal pages /squares/:id/*: loaded and kept up to date by SquareFrame, read by every page inside it.
export interface SquareContext {
  sq: Ref<PlatformSquare | null>
  /** replace the loaded square with the answer of a save */
  set: (v: PlatformSquare) => void
  reload: () => Promise<void>
}
const KEY = Symbol('portal-square')
export const provideSquare = (c: SquareContext) => provide(KEY, c)
export function useSquare(): SquareContext {
  const c = inject<SquareContext>(KEY)
  if (!c) throw new Error('useSquare() outside SquareFrame')
  return c
}
