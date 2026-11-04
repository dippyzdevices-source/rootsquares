// What the themed pages show, from the square's own data (rootsquares W9-R5). One shared store, filled once and only for the modules that are on:
// the header and footer ask for the basics (the square's words, contact details, the next event); the home page asks for the rest.
// A failed request just leaves its part empty; nothing here is critical.
import { computed, ref } from 'vue'
import { fetchEvents, type EventSummary } from '../services/eventsApi'
import { fetchAlbums, fetchGalleryMedia, type AlbumSummary, type GalleryMediaItem } from '../services/galleryApi'
import { fetchMembershipTypes, type MembershipTypeOption } from '../services/memberApi'
import { fetchNews, type NewsSummary } from '../services/newsApi'
import { moduleEnabled } from '../services/modules'
import { fetchSettings } from '../services/settingsApi'
import { fetchTestimonials, type Testimonial } from '../services/testimonialsApi'
import { EMPTY_HOME_CONTENT, loadHomeContent } from '../services/siteContent'

const home = ref({ ...EMPTY_HOME_CONTENT })
const email = ref('')
const phone = ref('')
const address = ref('')
const aboutText = ref('')
const heritageImage = ref<string | null>(null)
const events = ref<EventSummary[]>([])
const media = ref<GalleryMediaItem[]>([])
const albums = ref<AlbumSummary[]>([])
const news = ref<NewsSummary[]>([])
const tiers = ref<MembershipTypeOption[]>([])
const quotes = ref<Testimonial[]>([])
const quoteIndex = ref(0)
/** The testimonial on show (the visitor steps through them with the previous and next buttons, as on the default home page). */
const quote = computed<Testimonial | null>(() => (quotes.value.length ? quotes.value[quoteIndex.value % quotes.value.length]! : null))
function stepQuote(d: number): void {
  if (quotes.value.length) quoteIndex.value = (quoteIndex.value + d + quotes.value.length) % quotes.value.length
}
const basicsLoaded = ref(false)
const homeLoaded = ref(false)
let basicsAsked = false
let homeAsked = false

async function quietly<T>(run: () => Promise<T>): Promise<T | null> {
  try {
    return await run()
  } catch {
    return null
  }
}

/** The square's words, contact details and next events: everything the header, footer and navigation need. */
export function ensureBasics(): void {
  if (basicsAsked) return
  basicsAsked = true
  void loadHomeContent().then((content) => (home.value = content))
  void quietly(fetchSettings).then((settings) => {
    if (settings) {
      email.value = settings.contact_email
      phone.value = settings.contact_phone
      address.value = settings.contact_address
      aboutText.value = settings.about_text ?? ''
      heritageImage.value = settings.heritage_image_url ?? null
    }
    basicsLoaded.value = true
  })
  if (moduleEnabled('events')) void quietly(() => fetchEvents({ when: 'upcoming', perPage: 6 })).then((data) => (events.value = data?.items ?? []))
}

/** The parts of the home page. */
export function ensureHome(): void {
  ensureBasics()
  if (homeAsked) return
  homeAsked = true
  const jobs: Promise<unknown>[] = []
  if (moduleEnabled('gallery')) {
    jobs.push(quietly(() => fetchGalleryMedia(40, true)).then((items) => (media.value = items ?? [])))
    jobs.push(quietly(() => fetchAlbums(1, 9)).then((data) => (albums.value = data?.items ?? [])))
  }
  if (moduleEnabled('news')) jobs.push(quietly(() => fetchNews({ page: 1, perPage: 4 })).then((data) => (news.value = data?.items ?? [])))
  if (moduleEnabled('memberships')) jobs.push(quietly(fetchMembershipTypes).then((items) => (tiers.value = items ?? [])))
  if (moduleEnabled('testimonials')) jobs.push(quietly(fetchTestimonials).then((data) => {
    quotes.value = data?.items ?? []
  }))
  void Promise.all(jobs).then(() => (homeLoaded.value = true))
}

export function useSiteData() {
  return {
    home,
    email,
    phone,
    address,
    aboutText,
    heritageImage,
    events,
    media,
    albums,
    news,
    tiers,
    quote,
    quotes,
    stepQuote,
    basicsLoaded,
    homeLoaded,
    nextEvent: computed(() => events.value[0] ?? null),
    /** The albums as pictures (cover, title as caption, link to the album) for the gallery layouts. */
    albumPics: computed<GalleryMediaItem[]>(() => albums.value.map((a) => ({ id: a.id, filename: '', url: a.cover_thumbnail_url ?? '', thumbnail_url: a.cover_thumbnail_url ?? '', width: 0, height: 0, caption: a.title, album_id: a.id, album_title: a.title }))),
    /** The photos the page may use, newest random pick first; empty when the Gallery module is off or has no photos. */
    photos: computed(() => media.value),
    hasContact: computed(() => !!(email.value || phone.value || address.value)),
    /** The one main photo of a hero: a gallery photo, else the About photo; null shows the striped placeholder. */
    heroMain: computed(() => (moduleEnabled('gallery') ? media.value[0]?.url : undefined) ?? heritageImage.value),
    /** The secondary photos of a hero; none when the Gallery module is off (heroes then keep one photo). */
    heroThumbs: computed(() => (moduleEnabled('gallery') ? media.value.slice(1, 4) : [])),
  }
}
