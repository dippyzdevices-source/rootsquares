import { computed, onMounted, ref } from 'vue'
import { EMPTY_HOME_CONTENT, loadHomeContent, menuName, type PageHeading, type PageKey } from '../services/siteContent'

// The heading block of a public page (rootsquares W6-R75): the square's own words where it set them, else the page's neutral text. `defaults`
// can be a plain object or a function (when the neutral text uses something that changes). The script line and the own-language line have no
// default text: they show only when a square sets them.
export function usePageHeading(page: PageKey, defaults: Partial<PageHeading> | (() => Partial<PageHeading>)) {
  const content = ref({ ...EMPTY_HOME_CONTENT })
  onMounted(() => {
    void loadHomeContent().then((loaded) => (content.value = loaded))
  })
  return computed<PageHeading>(() => {
    const base = typeof defaults === 'function' ? defaults() : defaults
    const own = content.value.page_headings[page] ?? {}
    return {
      eyebrow: own.eyebrow || base.eyebrow || '',
      script_line: own.script_line || base.script_line || '',
      title: own.title || menuName(page, '') || base.title || '', // a page renamed in the menu is called that on its own page too (W11-R43)
      local_line: own.local_line || base.local_line || '',
      intro: own.intro || base.intro || '',
      nav_label: own.nav_label || '',
    }
  })
}
