import { computed, getCurrentInstance } from 'vue'

// The three high-level groups of the admin Settings area — the tabs of its strip and the groups of
// cards on its hub. Every Settings sub-page belongs to one of them.
export type SettingsGroupKey = 'site' | 'people' | 'pages' | 'lists'

// A group with `to` opens that page directly instead of the hub's cards (Lists is one editor page).
export const SETTINGS_GROUPS: { key: SettingsGroupKey; label: string; to?: string }[] = [
  { key: 'site', label: 'Site' },
  { key: 'people', label: 'People' },
  { key: 'pages', label: 'Pages & media' },
  { key: 'lists', label: 'Lists', to: '/admin/content/lists' },
]

const PATH_GROUP: [string, SettingsGroupKey][] = [
  ['/admin/content/settings', 'site'],
  ['/admin/content/contact-details', 'site'],
  ['/admin/content/typography', 'site'],
  ['/admin/content/payments', 'site'],
  ['/admin/content/header-footer', 'site'],
  ['/admin/content/legal-texts', 'pages'],
  ['/admin/content/home', 'pages'],
  ['/admin/content/page-headings', 'pages'],
  ['/admin/content/lists', 'lists'],
  ['/admin/content/committee', 'people'],
  ['/admin/content/founders', 'people'],
  ['/admin/content/heritage-image', 'pages'],
  ['/admin/content/sponsors', 'people'],
  ['/admin/content/pages', 'pages'],
]

export function groupForRoute(path: string, queryGroup: unknown): SettingsGroupKey {
  const hit = PATH_GROUP.find(([prefix]) => path === prefix || path.startsWith(prefix + '/'))
  if (hit) return hit[1]
  return SETTINGS_GROUPS.some((g) => g.key === queryGroup) ? (queryGroup as SettingsGroupKey) : 'site'
}

// The Back button of a Settings sub-page (W8-R4): none on the hub or on Lists, and none on a form (new / edit: those have their own Back to the list); everything else goes to its tab's cards.
export type SettingsBack = { to: string | { path: string; query: { group: SettingsGroupKey } }; label: string }
export function settingsBackTarget(path: string, group: SettingsGroupKey): SettingsBack | null {
  if (path === '/admin/content' || path === '/admin/content/' || group === 'lists') return null
  const form = path.match(/^(\/admin\/content\/[^/]+)\/(new|[^/]+\/edit)$/)
  if (form) return null
  const label = SETTINGS_GROUPS.find((g) => g.key === group)?.label ?? 'Settings'
  return { to: { path: '/admin/content', query: { group } }, label: `Back to ${label}` }
}

// Reads the router through the component instance (not useRoute()) so components that use it still
// mount in specs that mock vue-router or run without a router at all — they just resolve to 'site'.
export function useSettingsGroup() {
  const globals = getCurrentInstance()?.appContext.config.globalProperties as { $route?: { path: string; query: Record<string, unknown> } } | undefined
  return computed(() => {
    const route = globals?.$route
    return groupForRoute(route?.path ?? '/admin/content', route?.query?.group)
  })
}

export function useSettingsBack() {
  const globals = getCurrentInstance()?.appContext.config.globalProperties as { $route?: { path: string; query: Record<string, unknown> } } | undefined
  return computed(() => {
    const route = globals?.$route
    if (!route) return null
    return settingsBackTarget(route.path, groupForRoute(route.path, route.query?.group))
  })
}
