import { ref } from 'vue'
import { platform } from '@/services/platform'
import type { PortalAttention } from '@/services/platformTypes'

// What waits for the owner (W25-R35): one list for the whole portal. The layout refreshes it on every page change and once a minute (the count in the
// side bar); the strip on the dashboards reads the same list. A failed read keeps the old list (the page itself shows its own errors).
const items = ref<PortalAttention[]>([])

export async function refreshAttention(): Promise<void> {
  try { items.value = (await platform.getAttention()).items } catch { /* keep the old list */ }
}

export function useAttention() {
  return { items, refresh: refreshAttention }
}
