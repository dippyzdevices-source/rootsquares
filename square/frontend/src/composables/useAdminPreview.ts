import { readonly, ref } from 'vue'

// True while an admin is looking at a public page that the maintenance gate hides from
// everyone else (its Page visibility is "Admin"). Set by the router guard on each navigation
// and read by PublicLayout to show the "Admin preview" banner. Module-level singleton, same
// pattern as useToast()/useTheme() — not Pinia.
const active = ref(false)

export function setAdminPreview(value: boolean) {
  active.value = value
}

export function useAdminPreview() {
  return { adminPreviewActive: readonly(active) }
}
