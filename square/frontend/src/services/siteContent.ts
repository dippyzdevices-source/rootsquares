import { ref } from 'vue'
import { fetchSettings } from './settingsApi'

// The words a square sets for its home page, header and footer (rootsquares W6-R64; bca-oslo wrote its own into the page). Every key is optional:
// an empty one means the page shows its neutral text instead.
export interface HomeStat {
  value: string
  label: string
}

export type SocialNetwork = 'facebook' | 'instagram' | 'youtube'

export interface SocialLink {
  network: SocialNetwork
  url: string
}

export const SOCIAL_NETWORKS: SocialNetwork[] = ['facebook', 'instagram', 'youtube']

export type PageKey = 'events' | 'gallery' | 'news' | 'membership' | 'contact' | 'committee' | 'heritage'
export const PAGE_KEYS: PageKey[] = ['events', 'gallery', 'news', 'membership', 'contact', 'committee', 'heritage']

/** The heading block of a public page: small line, handwritten line, title, title in the community's own language, intro, and the page's name in the menu (W11-R43). */
export interface PageHeading {
  eyebrow: string
  script_line: string
  title: string
  local_line: string
  intro: string
  nav_label: string
}
export const PAGE_HEADING_FIELDS: (keyof PageHeading)[] = ['eyebrow', 'script_line', 'title', 'local_line', 'intro', 'nav_label']

// The names the square gave its public pages (W11-R43): "About" can be "Peek Us" in the menu, the footer and the browser tab. Reactive, so a menu that
// is already on screen changes when the words arrive. Empty until the square's words are loaded; an empty name means the page's own default.
const menuNames = ref<Partial<Record<PageKey, string>>>({})
/** The page's name in the menu: the square's own where it set one, else `fallback`. */
export function menuName(page: PageKey, fallback: string): string {
  return menuNames.value[page] || fallback
}
function rememberMenuNames(content: HomeContent): void {
  const names: Partial<Record<PageKey, string>> = {}
  for (const page of PAGE_KEYS) {
    const own = content.page_headings[page]?.nav_label
    if (own) names[page] = own
  }
  menuNames.value = names
}

/** The band at the bottom of the gallery page (W7-R4). No title = no band; no button label = no button; the coverage list is off unless chosen. */
export interface GalleryBand {
  eyebrow: string
  title: string
  text: string
  button_label: string
  show_coverage: boolean
}
export const EMPTY_GALLERY_BAND: GalleryBand = { eyebrow: '', title: '', text: '', button_label: '', show_coverage: false }

/** The newsletter band at the bottom of the news page, and whether the Magazines tab exists (W7-R5). No title = no band; magazines off unless chosen. */
export interface NewsBand {
  eyebrow: string
  title: string
  text: string
  consent: string
  show_magazines: boolean
}
export const EMPTY_NEWS_BAND: NewsBand = { eyebrow: '', title: '', text: '', consent: '', show_magazines: false }

/** A question and its answer below the contact form (W7-R9). */
export interface FaqItem {
  title: string
  content: string
}
/** The extra parts of the contact page (W7-R9). No questions = no section; empty footnote = no line. */
export interface ContactPage {
  faq_eyebrow: string
  faq_title: string
  faq: FaqItem[]
  footnote_text: string
  footnote_link: string
}
export const EMPTY_CONTACT_PAGE: ContactPage = { faq_eyebrow: '', faq_title: '', faq: [], footnote_text: '', footnote_link: '' }

/** One card under "who we are" and one row of the timeline on the About page (W7-R10). */
export interface AboutValue {
  title: string
  description: string
}
export interface AboutTimelineRow {
  year: string
  title: string
  description: string
}
/** The sections of the About page (W7-R10); each is shown only when it has words or rows. Founders come from the Founders list. */
export interface AboutPage {
  values_title: string
  values_button: string
  values: AboutValue[]
  what_title: string
  what_text: string
  what_membership_link: string
  what_events_link: string
  timeline_eyebrow: string
  timeline_title: string
  timeline: AboutTimelineRow[]
  involve_badge: string
  involve_title: string
  involve_text: string
  involve_button: string
}
export const EMPTY_ABOUT_PAGE: AboutPage = {
  values_title: '',
  values_button: '',
  values: [],
  what_title: '',
  what_text: '',
  what_membership_link: '',
  what_events_link: '',
  timeline_eyebrow: '',
  timeline_title: '',
  timeline: [],
  involve_badge: '',
  involve_title: '',
  involve_text: '',
  involve_button: '',
}

/** The two lists beside the membership types (W7-R11); a list with no rows is not shown. */
export interface MembershipPage {
  benefits_eyebrow: string
  benefits: { text: string }[]
  steps_eyebrow: string
  steps: { text: string }[]
}
export const EMPTY_MEMBERSHIP_PAGE: MembershipPage = { benefits_eyebrow: '', benefits: [], steps_eyebrow: '', steps: [] }

export interface HomeContent {
  eyebrow: string
  script_line: string
  headline: string
  local_line: string
  intro: string
  intro_name: string
  intro_suffix: string
  stats: HomeStat[]
  blurb: string
  /** The small line and the heading above the sponsors strip on the home page (W7-R6); both empty = the strip has no heading. */
  sponsors_eyebrow: string
  sponsors_title: string
  /** The words of the testimonial and association band on the home page (W7-R7); empty = not shown. */
  testimonials_eyebrow: string
  testimonials_empty_text: string
  testimonials_button: string
  association_eyebrow: string
  association_button: string
  utility_text: string
  tagline_local: string
  /** A line in the footer such as "Org. nr. 995757664". */
  footer_registration: string
  /** A short description under the name in the footer. */
  footer_blurb: string
  /** The whole copyright line; '' = the year and the name. */
  footer_copyright: string
  /** Links shown as icons under "Follow us" in the footer; none = nothing shown. */
  social_links: SocialLink[]
  /** The square's own heading words per public page (W6-R75); a page or a key not set shows the page's neutral text. */
  page_headings: Partial<Record<PageKey, Partial<PageHeading>>>
  /** The band at the bottom of the gallery page; nothing set = no band. */
  gallery_band: GalleryBand
  /** The newsletter band and the magazines choice on the news page; nothing set = no band, no Magazines tab. */
  news_band: NewsBand
  /** The questions and the footnote on the contact page; nothing set = neither shown. */
  contact_page: ContactPage
  /** The sections of the About page; nothing set = none shown. */
  about_page: AboutPage
  /** Why join and how to join on the Membership page; nothing set = neither shown. */
  membership_page: MembershipPage
  /** How big the logo is in the header and footer; '' = medium. */
  logo_size: '' | 'small' | 'medium' | 'large'
  /** How the name is written in the header and footer; '' = as written. 'caps' = capitals with a dot between the words. */
  name_style: '' | 'plain' | 'caps'
}

/** Height in pixels of the logo in the header and footer for each size (the width follows the logo's own shape). */
export const LOGO_HEIGHTS = { small: 32, medium: 44, large: 64 } as const

export function logoHeight(size: HomeContent['logo_size']): number {
  return size ? LOGO_HEIGHTS[size] : LOGO_HEIGHTS.medium
}

export const EMPTY_HOME_CONTENT: HomeContent = {
  eyebrow: '',
  script_line: '',
  headline: '',
  local_line: '',
  intro: '',
  intro_name: '',
  intro_suffix: '',
  stats: [],
  blurb: '',
  sponsors_eyebrow: '',
  sponsors_title: '',
  testimonials_eyebrow: '',
  testimonials_empty_text: '',
  testimonials_button: '',
  association_eyebrow: '',
  association_button: '',
  utility_text: '',
  tagline_local: '',
  footer_registration: '',
  footer_blurb: '',
  footer_copyright: '',
  social_links: [],
  page_headings: {},
  gallery_band: { ...EMPTY_GALLERY_BAND },
  news_band: { ...EMPTY_NEWS_BAND },
  contact_page: { ...EMPTY_CONTACT_PAGE },
  about_page: { ...EMPTY_ABOUT_PAGE },
  membership_page: { ...EMPTY_MEMBERSHIP_PAGE },
  logo_size: '',
  name_style: '',
}

export function fillHomeContent(content: Partial<HomeContent> | undefined): HomeContent {
  return { ...EMPTY_HOME_CONTENT, ...(content ?? {}), stats: content?.stats ?? [], social_links: content?.social_links ?? [], page_headings: content?.page_headings ?? {}, gallery_band: { ...EMPTY_GALLERY_BAND, ...(content?.gallery_band ?? {}) }, news_band: { ...EMPTY_NEWS_BAND, ...(content?.news_band ?? {}) }, contact_page: { ...EMPTY_CONTACT_PAGE, ...(content?.contact_page ?? {}), faq: content?.contact_page?.faq ?? [] }, about_page: { ...EMPTY_ABOUT_PAGE, ...(content?.about_page ?? {}), values: content?.about_page?.values ?? [], timeline: content?.about_page?.timeline ?? [] }, membership_page: { ...EMPTY_MEMBERSHIP_PAGE, ...(content?.membership_page ?? {}), benefits: content?.membership_page?.benefits ?? [], steps: content?.membership_page?.steps ?? [] } }
}

let cached: Promise<HomeContent> | null = null

/** The home content of this square, fetched once per page load and shared by the home page, header and footer. Empty when it cannot be loaded. */
export function loadHomeContent(): Promise<HomeContent> {
  cached ??= fetchSettings()
    .then((settings) => {
      const content = fillHomeContent(settings.home_content)
      rememberMenuNames(content)
      return content
    })
    .catch(() => {
      cached = null // try again next time
      return fillHomeContent(undefined)
    })
  return cached
}

/** Forget what was fetched (after an admin saved new words, and in tests). */
export function resetHomeContent(): void {
  cached = null
}
