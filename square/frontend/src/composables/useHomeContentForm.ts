import { ref } from 'vue'
import { fetchAdminSettings, updateAdminSettings, ValidationError } from '../services/adminSettingsApi'
import { EMPTY_HOME_CONTENT, PAGE_HEADING_FIELDS, PAGE_KEYS, SOCIAL_NETWORKS, fillHomeContent, resetHomeContent, type HomeContent, type SocialNetwork } from '../services/siteContent'
import { useToast } from './useToast'

// The words of a square (home_content) are edited on two admin pages: Header & footer, and Home page (rootsquares W6-R74). Both share this form.
// A page only changes its own keys: saving fetches the current content first and puts the page's own keys on top, so saving one page can never
// overwrite what the other page saved in the meantime.
const STAT_ROWS = 3
const FAQ_ROWS = 5
const ABOUT_VALUE_ROWS = 6
const ABOUT_TIMELINE_ROWS = 10
const MEMBERSHIP_ROWS = 6

export function useHomeContentForm(ownKeys: (keyof HomeContent)[], savedMessage: string) {
  const toast = useToast()
  const loading = ref(true)
  const saving = ref(false)
  const error = ref('')
  const form = ref<HomeContent>({ ...EMPTY_HOME_CONTENT })
  // One address per network in the form; saved as the list of the ones filled in (a link left empty is not shown).
  const social = ref<Record<SocialNetwork, string>>({ facebook: '', instagram: '', youtube: '' })

  function fill(content: Partial<HomeContent> | undefined) {
    const full = fillHomeContent(content)
    const stats = [...full.stats]
    while (stats.length < STAT_ROWS) stats.push({ value: '', label: '' })
    // every page and every heading key is present as text, so the form can edit them directly; empty ones are dropped by the server
    const headings: Record<string, Record<string, string>> = {}
    for (const page of PAGE_KEYS) {
      headings[page] = {}
      for (const field of PAGE_HEADING_FIELDS) headings[page]![field] = full.page_headings[page]?.[field] ?? ''
    }
    const values = [...full.about_page.values]
    while (values.length < ABOUT_VALUE_ROWS) values.push({ title: '', description: '' })
    const timeline = [...full.about_page.timeline]
    while (timeline.length < ABOUT_TIMELINE_ROWS) timeline.push({ year: '', title: '', description: '' })
    const benefits = [...full.membership_page.benefits]
    while (benefits.length < MEMBERSHIP_ROWS) benefits.push({ text: '' })
    const steps = [...full.membership_page.steps]
    while (steps.length < MEMBERSHIP_ROWS) steps.push({ text: '' })
    const faq = [...full.contact_page.faq]
    while (faq.length < FAQ_ROWS) faq.push({ title: '', content: '' })
    form.value = { ...full, stats, page_headings: headings as HomeContent['page_headings'], contact_page: { ...full.contact_page, faq }, about_page: { ...full.about_page, values, timeline }, membership_page: { ...full.membership_page, benefits, steps } }
    social.value = { facebook: '', instagram: '', youtube: '' }
    for (const link of full.social_links) social.value[link.network] = link.url
  }

  async function load() {
    try {
      fill((await fetchAdminSettings()).home_content)
    } catch {
      toast.error('Could not load the settings')
    } finally {
      loading.value = false
    }
  }

  async function save() {
    saving.value = true
    error.value = ''
    try {
      const current = fillHomeContent((await fetchAdminSettings()).home_content)
      const mine = { ...form.value, social_links: SOCIAL_NETWORKS.filter((n) => social.value[n].trim()).map((network) => ({ network, url: social.value[network].trim() })) }
      const merged: Record<string, unknown> = { ...current }
      for (const key of ownKeys) merged[key] = mine[key]
      fill((await updateAdminSettings({ home_content: merged as Partial<HomeContent> })).home_content)
      resetHomeContent()
      toast.success(savedMessage)
    } catch (err) {
      error.value = err instanceof ValidationError ? (err.errors.home_content ?? 'Please check the texts.') : 'Could not save'
    } finally {
      saving.value = false
    }
  }

  return { loading, saving, error, form, social, load, save }
}
