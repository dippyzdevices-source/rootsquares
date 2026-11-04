import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { DEFAULT_TENANT_THEME, isThemeId } from '@rootsquares/ui/themes'

// Theme id of the tenant site being previewed (from /site/:themeId).
export function useSite() {
  const route = useRoute()
  const themeId = computed(() => (isThemeId(route.params.themeId) ? route.params.themeId : DEFAULT_TENANT_THEME))
  const to = (path = '') => `/site/${themeId.value}${path}`
  return { themeId, to }
}
