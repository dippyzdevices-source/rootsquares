// Neutral sample data for demo mode (W10-R14). Invented, English, no real people, organisations or places; images are the neutral photos in public/demo
// (README there). Every constant is typed against the app's own interfaces, so a change to an API shape breaks the build here instead of the preview.
// Dates are computed from today, so the sample site never looks stale.
import type { EventDetail, EventSummary } from '../services/eventsApi'
import type { AlbumDetail, AlbumSummary, ArchiveCoverageEra, GalleryMediaItem, MediaItem } from '../services/galleryApi'
import type { NewsArticle, NewsSummary } from '../services/newsApi'
import type { CommitteeMember } from '../services/committeeApi'
import type { Founder } from '../services/foundersApi'
import type { Sponsor } from '../services/sponsorsApi'
import type { Testimonial } from '../services/testimonialsApi'
import type { Magazine } from '../services/magazinesApi'
import type { TicketTypeSummary } from '../services/ticketsApi'
import type { MembershipTypeOption } from '../services/memberApi'
import type { LookupItem } from '../services/lookupsApi'
import type { SiteSettings } from '../services/settingsApi'
import type { HomeContent } from '../services/siteContent'

export const DEMO_NAME = 'Sample Society'
const photo = (id: number) => `/demo/photo-${id}.jpg`

/** Start of today (UTC) plus `days`, at `hour` o'clock, as an ISO string. */
function at(days: number, hour = 18): string {
  const d = new Date()
  d.setUTCHours(hour, 0, 0, 0)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString()
}
const dateOnly = (days: number) => at(days, 12).slice(0, 10)

// ---- square configuration (GET /api/square/config) ----
export const demoConfig = (themeId: string) => ({
  slug: 'demo',
  name: DEMO_NAME,
  theme_id: themeId,
  currency: 'EUR',
  phone: { country: 'GB', name: 'United Kingdom', dial: '44', min_digits: 10, max_digits: 10, trunk_zero: true },
  logo_url: '',
  logo_dark_url: '',
  modules: ['events', 'payments', 'tickets', 'coupons', 'checkin', 'members', 'memberships', 'volunteering', 'accounting', 'gallery', 'news', 'magazines', 'newsletter', 'testimonials', 'sponsors', 'committee', 'founders', 'donations', 'messages'],
  // The auth host never answers (demo.invalid); the visitor is signed out and the sign-in pages show their own error.
  auth: { provider: 'supabase', url: 'https://demo.invalid', public_key: 'demo' },
})

// ---- lookups ----
export const LOOKUPS: Record<string, LookupItem[]> = {
  event_type: [{ value: 'festival', label: 'Festival' }, { value: 'cultural', label: 'Cultural' }, { value: 'community', label: 'Community' }, { value: 'other', label: 'Other' }],
  news_category: [{ value: 'announcement', label: 'Announcement' }, { value: 'story', label: 'Story' }, { value: 'blog', label: 'Blog' }],
  album_category: [{ value: 'festivals', label: 'Festivals' }, { value: 'cultural', label: 'Cultural' }, { value: 'community', label: 'Community' }, { value: 'archive', label: 'Archive' }],
  user_role: [{ value: 'member', label: 'Member' }, { value: 'volunteer', label: 'Volunteer' }, { value: 'admin', label: 'Admin' }],
  contact_reason: [{ value: 'general', label: 'General enquiry' }],
  ticket_age_category: [{ value: 'adult', label: 'Adult' }, { value: 'child', label: 'Child' }, { value: 'other', label: 'Other' }],
}

// ---- events ----
interface EventSeed { id: number; title: string; slug: string; days: number; hours: number; type: string; photo: number; venue: string; text: string; sub?: string }
const EVENT_SEEDS: EventSeed[] = [
  { id: 1, title: 'Autumn gathering at the hall', slug: 'autumn-gathering', days: 6, hours: 3, type: 'festival', photo: 17, venue: 'Sample Hall', sub: 'Our yearly get-together', text: 'An afternoon and evening of music, food and neighbours. Bring a friend, bring a dish if you like, and stay for the lantern walk.' },
  { id: 2, title: 'Open studio weekend', slug: 'open-studio-weekend', days: 13, hours: 6, type: 'community', photo: 20, venue: 'The Workshop, 4 Example Lane', text: 'Members open their workshops and kitchen tables: drop in, watch, try, ask. No booking needed for the open hours.' },
  { id: 3, title: 'Book club evening', slug: 'book-club-evening', days: 20, hours: 2, type: 'cultural', photo: 24, venue: 'Reading Room', text: 'This month we read something short and argue about it kindly. Tea and biscuits provided.' },
  { id: 4, title: 'Community café morning', slug: 'community-cafe-morning', days: 27, hours: 4, type: 'community', photo: 42, venue: 'Sample Hall, side room', text: 'A slow Saturday morning with coffee, home baking and a swap table for books and plants.' },
  { id: 5, title: 'Coastal walk', slug: 'coastal-walk', days: 41, hours: 3, type: 'community', photo: 12, venue: 'Meet at the old pier', text: 'An easy three-mile walk along the shore. Sturdy shoes, a flask and a good mood are all you need.' },
  { id: 6, title: 'Winter lights evening', slug: 'winter-lights-evening', days: 55, hours: 3, type: 'festival', photo: 18, venue: 'Sample Hall', text: 'Lanterns, soup and songs as the nights draw in. Families very welcome.' },
  { id: 7, title: 'Summer picnic', slug: 'summer-picnic', days: -30, hours: 4, type: 'community', photo: 13, venue: 'The Green', text: 'Blankets, baskets and a very long lunch.' },
  { id: 8, title: 'Harvest supper', slug: 'harvest-supper', days: -75, hours: 4, type: 'festival', photo: 19, venue: 'Sample Hall', text: 'A shared table of seasonal dishes cooked by members.' },
]
const summary = (s: EventSeed): EventSummary => ({
  id: s.id,
  title: s.title,
  slug: s.slug,
  short_description: s.text.split('. ')[0]!.replace(/\.$/, '') + '.',
  description_style: null,
  event_type: s.type,
  start_datetime: at(s.days, 17),
  end_datetime: at(s.days, 17 + s.hours),
  sales_closed: s.days < 0,
  sales_not_open: false,
  sales_open_at: null,
  venue: s.venue,
  banner_image: photo(s.photo),
  published: true,
})
export const EVENTS: EventSummary[] = EVENT_SEEDS.map(summary)
export const EVENT_DETAILS: EventDetail[] = EVENT_SEEDS.map((s) => ({
  ...summary(s),
  sub_name: s.sub ?? null,
  payment_methods: ['qr', 'cash'],
  sales_close_at: at(s.days, 15),
  cash_note: 'Pay at the door in cash.',
  facebook_url: null,
  instagram_url: null,
  max_tickets_per_email: 8,
  coupon_max_adult: null,
  coupon_max_child: null,
  description: `${s.text}\n\nEveryone is welcome, members and guests alike. Doors open half an hour before the start.`,
  address: s.venue,
  capacity: 120,
  status: 'published',
  banners: [{ id: s.id, image_url: photo(s.photo), sort_order: 0 }],
  sessions: s.id === 1
    ? [
        { id: 1, day_label: 'Saturday', time: '15:00', title: 'Doors and welcome drinks', description: null, sort_order: 0 },
        { id: 2, day_label: 'Saturday', time: '16:00', title: 'Music in the hall', description: 'Local players, all ages.', sort_order: 1 },
        { id: 3, day_label: 'Saturday', time: '18:30', title: 'Lantern walk', description: 'Leaves from the front steps.', sort_order: 2 },
      ]
    : [],
}))
export const TICKET_TYPES: Record<number, TicketTypeSummary[]> = Object.fromEntries(
  EVENT_SEEDS.filter((s) => s.days > 0 && s.id !== 4 && s.id !== 5).map((s) => [
    s.id,
    [
      { id: s.id * 10 + 1, name: 'Adult', description: null, price: 1500, capacity: 100, remaining: 64, sale_start: null, sale_end: null, valid_on: null, members_only: false, age_category: 'adult', coupon_eligible: false, status: 'on_sale' },
      { id: s.id * 10 + 2, name: 'Child (under 12)', description: null, price: 700, capacity: 40, remaining: 22, sale_start: null, sale_end: null, valid_on: null, members_only: false, age_category: 'child', coupon_eligible: false, status: 'on_sale' },
      { id: s.id * 10 + 3, name: 'Member', description: 'For members of the society.', price: 1000, capacity: 60, remaining: 31, sale_start: null, sale_end: null, valid_on: null, members_only: true, age_category: 'adult', coupon_eligible: false, status: 'on_sale' },
    ] satisfies TicketTypeSummary[],
  ]),
)
// Free events (café, walk) sell no tickets: an empty list.
for (const id of [4, 5]) TICKET_TYPES[id] = []

// ---- gallery ----
const media = (id: number, file: number, caption: string): MediaItem => ({ id, filename: `photo-${file}.jpg`, url: photo(file), thumbnail_url: photo(file), width: 1400, height: 900, caption })
interface AlbumSeed { id: number; title: string; description: string; category: string; yearsAgo: number; eventId: number | null; photos: [number, string][] }
const ALBUM_SEEDS: AlbumSeed[] = [
  { id: 1, title: 'Summer picnic', description: 'A long lunch on the green.', category: 'community', yearsAgo: 0, eventId: 7, photos: [[13, 'The shore at low tide'], [12, 'Rocks and calm water'], [16, 'Driftwood'], [18, 'Long grass in the sun'], [76, 'A bicycle by the shed']] },
  { id: 2, title: 'Harvest supper', description: 'Seasonal dishes at one long table.', category: 'festivals', yearsAgo: 0, eventId: 8, photos: [[102, 'Fresh raspberries'], [42, 'Coffee at the long table'], [19, 'Moss on an old trunk'], [17, 'The path to the hall']] },
  { id: 3, title: 'Open studio', description: 'Workshops and kitchen tables.', category: 'cultural', yearsAgo: 1, eventId: null, photos: [[20, 'A desk, ready for work'], [24, 'An open book'], [76, 'Parked outside'], [102, 'A snack break'], [42, 'Tea and a notebook']] },
  { id: 4, title: 'Walks and coastlines', description: 'Our favourite routes.', category: 'archive', yearsAgo: 3, eventId: null, photos: [[10, 'Above the bay'], [15, 'The waterfall'], [1018, 'Misty hills'], [13, 'A pebble shore'], [12, 'Where the rocks begin'], [16, 'Quiet water']] },
]
const thisYear = new Date().getUTCFullYear()
export const ALBUMS: AlbumSummary[] = ALBUM_SEEDS.map((a) => ({
  id: a.id,
  title: a.title,
  description: a.description,
  description_style: null,
  category: a.category,
  year: thisYear - a.yearsAgo,
  published: true,
  cover_thumbnail_url: photo(a.photos[0]![0]),
  cover_width: 1400,
  cover_height: 900,
  photo_count: a.photos.length,
}))
export const ALBUM_DETAILS: AlbumDetail[] = ALBUM_SEEDS.map((a) => ({
  id: a.id,
  title: a.title,
  description: a.description,
  description_style: null,
  event_id: a.eventId,
  category: a.category,
  published: true,
  media: a.photos.map(([file, caption], i) => media(a.id * 100 + i, file, caption)),
}))
export const GALLERY_MEDIA: GalleryMediaItem[] = ALBUM_DETAILS.flatMap((a) => a.media.map((m) => ({ ...m, album_id: a.id, album_title: a.title })))
export const COVERAGE: ArchiveCoverageEra[] = [
  { era: 'The early years', start_year: thisYear - 30, end_year: thisYear - 21, photo_count: 0, state: 'none' },
  { era: 'Growing up', start_year: thisYear - 20, end_year: thisYear - 11, photo_count: 14, state: 'very_few' },
  { era: 'The hall years', start_year: thisYear - 10, end_year: thisYear - 4, photo_count: 85, state: 'partial' },
  { era: 'Recent years', start_year: thisYear - 3, end_year: thisYear, photo_count: 240, state: 'complete' },
]

// ---- news ----
interface NewsSeed { id: number; title: string; slug: string; category: string; author: string; days: number; photo: number; summary: string; body: string }
const NEWS_SEEDS: NewsSeed[] = [
  { id: 1, title: 'A new season begins', slug: 'a-new-season-begins', category: 'announcement', author: 'The committee', days: -4, photo: 24, summary: 'Autumn brings a full programme, from the gathering at the hall to winter lights.', body: 'The new season is here, and the calendar is fuller than ever.\n\nWe start with the autumn gathering at the hall, then an open studio weekend, a book club evening and a slow café morning. Winter closes with the lights evening.\n\nAll dates are on the Events page. Members get the first look at tickets.' },
  { id: 2, title: 'Behind the scenes at the open studio', slug: 'behind-the-scenes-open-studio', category: 'story', author: 'A. Sample', days: -12, photo: 20, summary: 'Six members, six workshops, one weekend: what to expect when the doors open.', body: 'Every year a handful of members open their workshops to everyone.\n\nYou might see a weaver at the loom, a baker at the bench or someone mending a very old chair. Questions are encouraged and so are small purchases.\n\nBring a bag and some curiosity.' },
  { id: 3, title: 'Thank you, picnic helpers', slug: 'thank-you-picnic-helpers', category: 'blog', author: 'J. Example', days: -33, photo: 16, summary: 'The summer picnic ran smoothly because of a dozen quiet volunteers.', body: 'It looked effortless, which is exactly how you know many people worked hard.\n\nThank you to everyone who carried tables, boiled kettles and cleared up after dark. See you next summer.' },
  { id: 4, title: 'Walking routes you may not know', slug: 'walking-routes', category: 'story', author: 'The walking group', days: -50, photo: 15, summary: 'Three short routes from our archive, with notes from people who have walked them for years.', body: 'The shore path, the waterfall loop and the misty ridge are our favourites.\n\nEach takes under two hours at an easy pace. We have added maps to the next newsletter.' },
]
const newsSummary = (n: NewsSeed): NewsSummary => ({ id: n.id, title: n.title, slug: n.slug, summary: n.summary, description_style: null, banner_image: photo(n.photo), category: n.category, author: n.author, read_minutes: 3, published_at: at(n.days, 9), published: true })
export const NEWS: NewsSummary[] = NEWS_SEEDS.map(newsSummary)
export const NEWS_ARTICLES: NewsArticle[] = NEWS_SEEDS.map((n) => ({ ...newsSummary(n), content: n.body, images: [] }))

// ---- people and partners ----
export const COMMITTEE: CommitteeMember[] = [
  { id: 1, name: 'Alex Sample', sub_name: null, role: 'Chair', portrait_url: null, address: null, email: null, phone: null, member_since: thisYear - 9, quote: 'A good society is mostly good habits.', published: true },
  { id: 2, name: 'Jo Example', sub_name: null, role: 'Vice chair', portrait_url: null, address: null, email: null, phone: null, member_since: thisYear - 7, quote: null, published: true },
  { id: 3, name: 'Sam Placeholder', sub_name: null, role: 'Treasurer', portrait_url: null, address: null, email: null, phone: null, member_since: thisYear - 6, quote: 'Every receipt has a story.', published: true },
  { id: 4, name: 'Robin Demo', sub_name: null, role: 'Secretary', portrait_url: null, address: null, email: null, phone: null, member_since: thisYear - 4, quote: null, published: true },
  { id: 5, name: 'Kim Sketch', sub_name: null, role: 'Events lead', portrait_url: null, address: null, email: null, phone: null, member_since: thisYear - 3, quote: null, published: true },
  { id: 6, name: 'Taylor Mockup', sub_name: null, role: 'Communications', portrait_url: null, address: null, email: null, phone: null, member_since: thisYear - 2, quote: null, published: true },
]
export const FOUNDERS: Founder[] = [
  { id: 1, name: 'First Founder', sub_name: null, role: 'Founding member', quote: 'We only wanted a room with a kettle. It turned into this.', portrait_url: null, published: true },
  { id: 2, name: 'Second Founder', sub_name: null, role: 'Founding member', quote: 'Start small, invite everyone, and keep the tea hot.', portrait_url: null, published: true },
]
export const SPONSORS: Sponsor[] = [
  { id: 1, name: 'Example Bakery', logo_url: null, website_url: null, published: true },
  { id: 2, name: 'Sample Print Shop', logo_url: null, website_url: null, published: true },
  { id: 3, name: 'Placeholder Books', logo_url: null, website_url: null, published: true },
]
export const TESTIMONIALS: Testimonial[] = [
  { id: 1, quote: 'I came for one evening and stayed for the people. It feels like a second living room.', author_name: 'A member', author_context: 'Member since last year', photo_url: null, published: true },
  { id: 2, quote: 'The events are warm, well run and never stuffy. My children ask when the next one is.', author_name: 'A parent', author_context: 'Family member', photo_url: null, published: true },
  { id: 3, quote: 'Volunteering here taught me more about my own town than ten years of living in it.', author_name: 'A volunteer', author_context: null, photo_url: null, published: true },
]
export const MAGAZINES: Magazine[] = [
  { id: 1, title: 'The Gathering', slug: 'the-gathering-autumn', issue_label: 'Autumn issue', issue_date: dateOnly(-20), description: 'Stories, recipes and a pull-out calendar.', description_style: null, pdf_url: null, cover_url: photo(1018), published: true },
  { id: 2, title: 'The Gathering', slug: 'the-gathering-summer', issue_label: 'Summer issue', issue_date: dateOnly(-110), description: 'Picnic photos and walking routes.', description_style: null, pdf_url: null, cover_url: photo(10), published: true },
]
export const MEMBERSHIP_TYPES: MembershipTypeOption[] = [
  { name: 'Individual', price: 3000, billing_frequency: 'yearly', contact_for_price: false, description: 'For one adult. Member prices on tickets and a vote at the yearly meeting.' },
  { name: 'Family', price: 5000, billing_frequency: 'yearly', contact_for_price: false, description: 'For two adults and their children under 18.' },
  { name: 'Supporter', price: null, billing_frequency: 'yearly', contact_for_price: true, description: 'Give a little more to keep the hall open. Get in touch and we will agree an amount.' },
]

// ---- site settings (GET /api/settings) ----
const homeContent: Partial<HomeContent> = {
  eyebrow: 'Welcome',
  script_line: 'Come as you are',
  headline: 'A place to meet, make and share',
  local_line: '',
  intro: 'A friendly society for neighbours who like good company, good food and a good reason to leave the house. This is',
  intro_name: DEMO_NAME,
  intro_suffix: 'Everyone is welcome.',
  stats: [{ value: '120', label: 'Members' }, { value: '30+', label: 'Events a year' }, { value: '9', label: 'Years together' }],
  blurb: 'We run seasonal gatherings, open workshops, a book club and a community café, all from one small hall.',
  sponsors_eyebrow: 'With thanks to',
  sponsors_title: 'Our local supporters',
  testimonials_eyebrow: 'Kind words',
  testimonials_empty_text: 'Be the first to share what the society means to you.',
  testimonials_button: 'Share your words',
  association_eyebrow: 'Part of the community?',
  association_button: 'Become a member',
  utility_text: '',
  tagline_local: '',
  footer_registration: 'Registered society no. 000000',
  footer_blurb: 'A friendly society for neighbours.',
  footer_copyright: '',
  social_links: [],
  page_headings: {
    events: { eyebrow: 'What is on', script_line: 'Save the date', title: 'Events', intro: 'Gatherings, workshops and walks, open to members and guests.' },
    gallery: { eyebrow: 'Our memories', title: 'Gallery', intro: 'Photographs from our events over the years.' },
    news: { eyebrow: 'From the committee', title: 'News and stories', intro: 'Announcements, stories and thank-yous.' },
    membership: { eyebrow: 'Join us', title: 'Membership', intro: 'Pick the membership that suits you.' },
    contact: { eyebrow: 'Say hello', title: 'Contact', intro: 'Questions, ideas or offers of help: we would love to hear from you.' },
    committee: { eyebrow: 'The people', title: 'Committee', intro: 'Volunteers who keep everything running.' },
    heritage: { eyebrow: 'Our story', title: 'About us', intro: 'How a kettle and a room became a society.' },
  },
  gallery_band: { eyebrow: 'The archive', title: 'Photos from every era', text: 'Some years are well covered, others are waiting for your shoebox of prints.', button_label: 'Get in touch', show_coverage: true },
  news_band: { eyebrow: 'Stay in the loop', title: 'The newsletter', text: 'One short email a month with what is coming up.', consent: 'I agree to receive the newsletter.', show_magazines: true },
  contact_page: {
    faq_eyebrow: 'Good to know',
    faq_title: 'Common questions',
    faq: [
      { title: 'Do I have to be a member to come?', content: 'No. Most events are open to everyone; members simply pay a little less.' },
      { title: 'Can I volunteer?', content: 'Yes, please. Tell us what you enjoy and we will find a role.' },
    ],
    footnote_text: 'Prefer to talk?',
    footnote_link: 'hello@example.org',
  },
  about_page: {
    values_title: 'Who we are',
    values_button: 'Meet the committee',
    values: [
      { title: 'Open doors', description: 'Everyone is welcome, whether they live next door or just arrived.' },
      { title: 'Shared tables', description: 'Food and conversation bring people together better than speeches.' },
      { title: 'Many hands', description: 'We are run by volunteers, and we like it that way.' },
    ],
    what_title: 'What we do',
    what_text: 'Seasonal gatherings, open workshops, a monthly book club and a weekly community café.',
    what_membership_link: 'Become a member',
    what_events_link: 'See what is on',
    timeline_eyebrow: 'Our journey',
    timeline_title: 'A few milestones',
    timeline: [
      { year: String(thisYear - 9), title: 'A first meeting', description: 'Six people, one kettle, one borrowed room.' },
      { year: String(thisYear - 6), title: 'The hall', description: 'We took on the lease of our own small hall.' },
      { year: String(thisYear - 3), title: 'The first open studio', description: 'Members opened their workshops to the town.' },
      { year: String(thisYear), title: 'Today', description: 'A hundred and twenty members and a full calendar.' },
    ],
    involve_badge: 'Get involved',
    involve_title: 'There is room for you',
    involve_text: 'Bake, host, photograph, fix things or simply turn up.',
    involve_button: 'Get in touch',
  },
  membership_page: {
    benefits_eyebrow: 'Why join',
    benefits: [{ text: 'Lower ticket prices at every event' }, { text: 'A vote at the yearly meeting' }, { text: 'First look at new events' }, { text: 'The seasonal magazine' }],
    steps_eyebrow: 'How to join',
    steps: [{ text: 'Choose a membership below' }, { text: 'Pay online or in cash at the next event' }, { text: 'Receive your welcome email' }],
  },
  logo_size: '',
  name_style: '',
}
export const SETTINGS: SiteSettings = {
  contact_email: 'hello@example.org',
  contact_phone: '',
  contact_address: '12 Sample Street, Exampleton',
  timezone: 'UTC',
  maintenance_mode: false,
  maintenance_allowed_event_slugs: '',
  maintenance_allowed_page_paths: '',
  maintenance_hidden_page_paths: '',
  heritage_image_url: photo(1018),
  description_style: 'karla',
  privacy_text: 'This is a demonstration site. It collects nothing and stores nothing.',
  terms_text: 'This is a demonstration site. Nothing can be bought here.',
  about_text: 'Sample Society began with a kettle and a borrowed room. Today it is a friendly society of neighbours who run seasonal gatherings, open workshops, a book club and a community café.\n\nWe are run entirely by volunteers and open to everyone.',
  home_content: homeContent,
  vipps_qr_enabled: false,
  vipps_qr_available: false,
  vipps_number: null,
  cash_enabled: true,
  cash_ticket_note: 'Pay at the door in cash.',
  cash_membership_note: 'Pay in cash at the next event.',
}
