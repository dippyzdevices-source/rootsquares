// Shared rules of the themed site (rootsquares W9-R5): the module rules of the design prompt, the compact breakpoint, and small helpers.
//   Gallery off  -> no nav link, no home section, no hero photo strip.
//   Events off   -> no nav link, no programme; the "Up next" card becomes a membership card (or goes if Membership is off too); the second button
//                   falls back to Heritage.
//   Membership off -> every "Become a member" reads "Get in touch" and goes to Contact.
//   News off     -> no nav link, no home section.  Home, Heritage (About) and Contact are core and always on.
import { computed, ref } from 'vue'
import { moduleEnabled } from '../services/modules'
import { menuName } from '../services/siteContent'
import { COMPACT_BELOW, activeLayout, type SectionKey } from './layouts'
import { useSiteData } from './useSiteData'

/** True while the site container is narrower than COMPACT_BELOW; kept up to date by LayoutShell. */
export const compact = ref(typeof window !== 'undefined' ? window.innerWidth < COMPACT_BELOW : false)
/** True from 1280 px: the capitals-navigation bars have room for the main button as well. */
export const wide = ref(typeof window !== 'undefined' ? window.innerWidth >= 1280 : false)
/** True under 1100 px: the bar headers tighten their links and drop the button. */
export const medium = ref(typeof window !== 'undefined' ? window.innerWidth < 1100 : false)

export interface NavItem {
  key: 'home' | 'events' | 'heritage' | 'gallery' | 'membership' | 'news' | 'contact' | 'donate' | 'newsletter'
  label: string
  to: string
}

const SECTION_MODULE: Record<SectionKey, Parameters<typeof moduleEnabled>[0]> = {
  events: 'events',
  heritage: undefined,
  gallery: 'gallery',
  news: 'news',
  membership: 'memberships',
}
export const sectionOn = (key: SectionKey): boolean => moduleEnabled(SECTION_MODULE[key])

export const eventsOn = moduleEnabled('events')
export const galleryOn = moduleEnabled('gallery')
export const membershipOn = moduleEnabled('memberships')
export const newsOn = moduleEnabled('news')
export const testimonialsOn = moduleEnabled('testimonials')
export const sponsorsOn = moduleEnabled('sponsors')

// `label` is a getter: the square's own name for the page where it set one (W11-R43), else the default; reactive, so every shell follows.
const navItem = (key: NavItem['key'], label: string, to: string): NavItem => ({
  key,
  to,
  get label() {
    return key === 'home' || key === 'donate' || key === 'newsletter' ? label : menuName(key, label)
  },
})
const ALL_NAV: NavItem[] = [
  navItem('home', 'Home', '/'),
  navItem('events', 'Events', '/events'),
  navItem('heritage', 'About', '/about'),
  navItem('gallery', 'Gallery', '/gallery'),
  navItem('membership', 'Membership', '/membership'),
  navItem('news', 'News', '/news'),
  navItem('contact', 'Contact', '/contact'),
  navItem('donate', 'Donate', '/donate'),
  navItem('newsletter', 'Newsletter', '/newsletter'),
]
// Donate follows the Donations module; the Newsletter link is only there when News is off, because the sign-up band then sits under the news list (W14-R13, W14-R21)
const extraOn = (key: NavItem['key']): boolean => (key === 'donate' ? moduleEnabled('donations') : key === 'newsletter' ? moduleEnabled('newsletter') && !moduleEnabled('news') : false)
const isShown = (item: NavItem): boolean => {
  if (item.key === 'donate' || item.key === 'newsletter') return extraOn(item.key)
  if (item.key === 'home' || item.key === 'contact') return moduleEnabled(item.key)
  if (item.key === 'heritage') return moduleEnabled('about')
  return sectionOn(item.key as SectionKey)
}
export const navItems: NavItem[] = ALL_NAV.filter(isShown)

export interface Cta {
  label: string
  to: string
}
/** The main button: Become a member, or Get in touch when Membership is off. */
export const cta: Cta = membershipOn ? { label: 'Become a member', to: '/membership' } : { label: 'Get in touch', to: '/contact' }
/** The second button: the programme, else Heritage (always there). */
export const cta2: Cta = eventsOn ? { label: 'See the programme', to: '/events' } : { label: 'Our story', to: '/about' }

/** The headline in three parts, the middle one emphasised. One word: emphasised alone; two: first, then emphasised. */
export function headlineParts(text: string): [string, string, string] {
  const words = text.trim().split(/\s+/).filter(Boolean)
  const n = words.length
  if (n === 0) return ['', '', '']
  if (n === 1) return [words[0]!, '', '']
  if (n === 2) return [words[0]!, words[1]!, '']
  const edge = Math.max(1, Math.floor(n / 3))
  return [words.slice(0, edge).join(' '), words.slice(edge, n - edge).join(' '), words.slice(n - edge).join(' ')]
}

export function dayMonth(iso: string): { day: string; month: string; year: string } {
  const d = new Date(iso)
  return {
    day: String(d.getDate()),
    month: d.toLocaleDateString('en-GB', { month: 'short' }),
    year: String(d.getFullYear()),
  }
}

export function timeOf(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

/** Everything a shell, hero or section needs about this layout, in one place. */
export function useSiteLayout() {
  const data = useSiteData()
  const home = data.home
  const name = computed(() => home.value.headline || '')
  const headline = computed(() => headlineParts(home.value.headline))
  return {
    layout: activeLayout!,
    compact,
    data,
    name,
    headline,
    nav: navItems,
    cta,
    cta2,
    stats: computed(() => home.value.stats),
  }
}
