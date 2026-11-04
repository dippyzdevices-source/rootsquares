import { onMounted, ref } from 'vue'
import { fetchSettings } from '../services/settingsApi'

/** The picture of the square's own Vipps QR code (W16-R8); null while there is none or it is not loaded yet. */
export function useVippsQrImage() {
  const image = ref<string | null>(null)
  onMounted(() => {
    void fetchSettings()
      .then((settings) => {
        image.value = settings.vipps_qr_image_url ?? null
      })
      .catch(() => {
        image.value = null
      })
  })
  return image
}

/** The square's own Vipps number (a setting, rootsquares W6-R38); null while it is not set or not loaded yet. */
export function useVippsNumber() {
  const vippsNumber = ref<string | null>(null)
  onMounted(() => {
    void fetchSettings()
      .then((settings) => {
        vippsNumber.value = settings.vipps_number ?? null
      })
      .catch(() => {
        vippsNumber.value = null
      })
  })
  return vippsNumber
}
