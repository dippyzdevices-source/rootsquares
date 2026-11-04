import { ref } from 'vue'
import { platform } from '@/services/platform'

// The countries whose tax is inside the listed prices (W13-R51): asked once, then kept. Empty until it arrives or when the server cannot be asked.
export const taxRates = ref<Record<string, number>>({})
let asked = false
export function loadTaxRates() {
  if (asked) return
  asked = true
  platform.getTaxRates().then((r) => { taxRates.value = r }).catch(() => { asked = false })
}
