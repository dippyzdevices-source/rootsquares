// Mock data for the demo tenant: BCA Oslo (Bengali Cultural Association). All of it is invented sample data.

export type EventStatus = 'live' | 'draft'
export interface TicketType { id: string; label: string; price: number }
export interface BcaEvent {
  id: string
  title: string
  date: string // ISO
  dateLabel: string
  day: string
  month: string
  place: string
  status: EventStatus
  sold: number
  capacity: number
  tag: string
  summary: string
  tickets: TicketType[]
}

export const ORG = { name: 'BCA Oslo', fullName: 'Bengali Cultural Association, Oslo', email: 'post@bca-oslo.example', place: 'Furuset Forum, Oslo' }

export const events: BcaEvent[] = [
  {
    id: 'mahalaya', title: 'Mahalaya', date: '2026-10-10T05:30', dateLabel: 'Sat 10 Oct 2026 · 05:30', day: '10', month: 'OCT',
    place: 'Furuset Forum, Oslo', status: 'live', sold: 62, capacity: 80, tag: 'Festival',
    summary: 'We open the Pujo season at dawn with the Mahalaya recital, followed by tea and mishti. Bring a shawl: the hall is cool at that hour.',
    tickets: [{ id: 'member', label: 'Member', price: 0 }, { id: 'guest', label: 'Guest', price: 100 }, { id: 'child', label: 'Child under 12', price: 0 }],
  },
  {
    id: 'durga-puja', title: 'Durga Puja', date: '2026-10-17T10:00', dateLabel: 'Sat 17 to Mon 19 Oct 2026 · 10:00', day: '17', month: 'OCT',
    place: 'Furuset Forum, Oslo', status: 'live', sold: 214, capacity: 300, tag: 'Festival',
    summary: 'Three days of anjali, bhog, cultural evenings and the dhunuchi naach. Everyone is welcome at the table.',
    tickets: [{ id: 'member', label: 'Member (3 days)', price: 300 }, { id: 'guest', label: 'Guest (3 days)', price: 450 }, { id: 'family', label: 'Family of four', price: 900 }, { id: 'child', label: 'Child under 12', price: 150 }],
  },
  {
    id: 'saraswati-puja', title: 'Saraswati Puja', date: '2027-01-23T11:00', dateLabel: 'Sat 23 Jan 2027 · 11:00', day: '23', month: 'JAN',
    place: 'Grorud Bydelshus, Oslo', status: 'live', sold: 18, capacity: 120, tag: 'Festival',
    summary: 'Children begin their year of learning with books and pens at the feet of the goddess. Khichuri bhog for all afterwards.',
    tickets: [{ id: 'member', label: 'Member', price: 100 }, { id: 'guest', label: 'Guest', price: 150 }, { id: 'child', label: 'Child under 12', price: 0 }],
  },
  {
    id: 'rabindra-jayanti', title: 'Rabindra Jayanti', date: '2027-05-08T17:00', dateLabel: 'Sat 8 May 2027 · 17:00', day: '08', month: 'MAY',
    place: 'Furuset Forum, Oslo', status: 'draft', sold: 0, capacity: 150, tag: 'Concert',
    summary: 'An evening of Tagore songs, recitation and dance to mark his birthday. Programme still being planned.',
    tickets: [{ id: 'member', label: 'Member', price: 150 }, { id: 'guest', label: 'Guest', price: 250 }, { id: 'child', label: 'Child under 12', price: 0 }],
  },
]

export type FeeStatus = 'paid' | 'pending' | 'overdue'
export type MemberType = 'Full member' | 'Family' | 'Student' | 'Honorary'
export interface Member { id: number; name: string; kind: MemberType; since: string; fee: FeeStatus; email: string }

const FIRST = ['Anirban', 'Sreya', 'Debasish', 'Moumita', 'Rahul', 'Ishita', 'Subhajit', 'Tanushree', 'Arindam', 'Rupa', 'Kaushik', 'Piyali', 'Soumen', 'Mitali', 'Sayan', 'Nandini', 'Partha', 'Anwesha', 'Biswajit', 'Madhumita']
const LAST = ['Banerjee', 'Chatterjee', 'Mukherjee', 'Bose', 'Dasgupta', 'Sen', 'Ghosh', 'Roy', 'Das', 'Mitra']
const KINDS: MemberType[] = ['Full member', 'Full member', 'Family', 'Student', 'Full member', 'Family', 'Honorary', 'Student']
const FEES: FeeStatus[] = ['paid', 'paid', 'paid', 'pending', 'paid', 'overdue', 'paid', 'paid', 'pending', 'paid']

export const members: Member[] = Array.from({ length: 40 }, (_, i) => {
  const name = `${FIRST[i % FIRST.length]} ${LAST[(i * 3 + 1) % LAST.length]}`
  return {
    id: i + 1,
    name,
    kind: KINDS[i % KINDS.length]!,
    since: String(2012 + ((i * 7) % 14)),
    fee: FEES[i % FEES.length]!,
    email: `${name.toLowerCase().replace(/[^a-z]+/g, '.')}@example.no`,
  }
})

export interface CommitteeMember { id: number; name: string; role: string; email: string; bio?: string; visible: boolean; portrait?: string }
export const committee: CommitteeMember[] = [
  { id: 1, name: 'Sreya Chatterjee', role: 'President', email: 'president@bca-oslo.example', bio: '', visible: true },
  { id: 2, name: 'Anirban Banerjee', role: 'Vice president', email: 'vice@bca-oslo.example', bio: '', visible: true },
  { id: 3, name: 'Moumita Das', role: 'Secretary', email: 'secretary@bca-oslo.example', bio: '', visible: true },
  { id: 4, name: 'Debasish Ghosh', role: 'Treasurer', email: 'treasurer@bca-oslo.example', bio: '', visible: true },
  { id: 5, name: 'Piyali Sen', role: 'Cultural lead', email: 'culture@bca-oslo.example', bio: '', visible: true },
  { id: 6, name: 'Rahul Mitra', role: 'Youth and school', email: 'youth@bca-oslo.example', bio: '', visible: true },
]

export type OrderStatus = 'paid' | 'pending' | 'overdue'
export interface Order { id: number; name: string; eventId: string; event: string; total: number; status: OrderStatus; date: string; ref?: string }
export const orders: Order[] = [
  { id: 1042, name: 'Anirban Banerjee', eventId: 'durga-puja', event: 'Durga Puja', total: 900, status: 'pending', date: '2026-10-05' },
  { id: 1041, name: 'Ishita Roy', eventId: 'durga-puja', event: 'Durga Puja', total: 450, status: 'pending', date: '2026-10-05' },
  { id: 1040, name: 'Subhajit Bose', eventId: 'mahalaya', event: 'Mahalaya', total: 200, status: 'overdue', date: '2026-09-28' },
  { id: 1039, name: 'Tanushree Sen', eventId: 'durga-puja', event: 'Durga Puja', total: 300, status: 'paid', date: '2026-09-27', ref: '4821' },
  { id: 1038, name: 'Arindam Dasgupta', eventId: 'durga-puja', event: 'Durga Puja', total: 900, status: 'paid', date: '2026-09-26', ref: '4807' },
  { id: 1037, name: 'Rupa Mukherjee', eventId: 'mahalaya', event: 'Mahalaya', total: 100, status: 'paid', date: '2026-09-25', ref: '4799' },
  { id: 1036, name: 'Kaushik Das', eventId: 'durga-puja', event: 'Durga Puja', total: 600, status: 'paid', date: '2026-09-24', ref: '4790' },
  { id: 1035, name: 'Piyali Ghosh', eventId: 'saraswati-puja', event: 'Saraswati Puja', total: 250, status: 'paid', date: '2026-09-22', ref: '4776' },
  { id: 1034, name: 'Soumen Mitra', eventId: 'durga-puja', event: 'Durga Puja', total: 450, status: 'paid', date: '2026-09-21', ref: '4768' },
  { id: 1033, name: 'Mitali Roy', eventId: 'mahalaya', event: 'Mahalaya', total: 100, status: 'paid', date: '2026-09-20', ref: '4755' },
  { id: 1032, name: 'Sayan Sen', eventId: 'durga-puja', event: 'Durga Puja', total: 300, status: 'pending', date: '2026-09-19' },
  { id: 1031, name: 'Nandini Bose', eventId: 'durga-puja', event: 'Durga Puja', total: 150, status: 'paid', date: '2026-09-18', ref: '4731' },
]

export interface LedgerEntry { id: number; date: string; what: string; amount: number }
export const ledger: LedgerEntry[] = [
  { id: 1, date: '2026-10-05', what: 'Ticket sales: Durga Puja', amount: 12600 },
  { id: 2, date: '2026-10-02', what: 'Hall deposit: Furuset Forum', amount: -4000 },
  { id: 3, date: '2026-09-30', what: 'Membership fees (14)', amount: 5600 },
  { id: 4, date: '2026-09-27', what: 'Puja decoration and flowers', amount: -3150 },
  { id: 5, date: '2026-09-25', what: 'Ticket sales: Mahalaya', amount: 1800 },
  { id: 6, date: '2026-09-18', what: 'Sound system hire', amount: -2200 },
  { id: 7, date: '2026-09-10', what: 'Printing: posters and programme', amount: -850 },
  { id: 8, date: '2026-09-01', what: 'Sponsorship: local restaurant', amount: 5000 },
]

export const monthly = {
  categories: ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'],
  income: [9000, 4000, 2000, 3000, 14000, 14400],
  expenses: [6000, 2500, 1000, 1500, 7200, 6150],
}

export const invoices = [
  { id: 1, month: 'Oct 2026', amount: '$25', status: 'pending' as const },
  { id: 2, month: 'Sep 2026', amount: '$25', status: 'paid' as const },
  { id: 3, month: 'Aug 2026', amount: '$25', status: 'paid' as const },
]

export interface TenantRow { id: number; name: string; plan: 'Small club' | 'Community' | 'Federation'; status: 'live' | 'trial' | 'overdue' | 'draft'; members: number; since: string; country: string; mrr: number }
export const tenants: TenantRow[] = [
  { id: 1, name: 'BCA Oslo', plan: 'Community', status: 'live', members: 40, since: '2026-05', country: 'Norway', mrr: 199 },
  { id: 2, name: 'Åland Kulturförening', plan: 'Community', status: 'live', members: 212, since: '2026-03', country: 'Finland', mrr: 199 },
  { id: 3, name: 'Bergen Norwegian-Tamil School', plan: 'Small club', status: 'live', members: 48, since: '2026-06', country: 'Norway', mrr: 99 },
  { id: 4, name: 'Malmö Polska Förening', plan: 'Community', status: 'trial', members: 71, since: '2026-09', country: 'Sweden', mrr: 0 },
  { id: 5, name: 'Københavns Urdu Klub', plan: 'Small club', status: 'overdue', members: 33, since: '2026-02', country: 'Denmark', mrr: 99 },
  { id: 6, name: 'Nordic Sikh Federation', plan: 'Federation', status: 'live', members: 540, since: '2026-01', country: 'Sweden', mrr: 399 },
  { id: 7, name: 'Helsinki Language Café', plan: 'Small club', status: 'trial', members: 19, since: '2026-09', country: 'Finland', mrr: 0 },
  { id: 8, name: 'Trondheim Sufi Circle', plan: 'Small club', status: 'draft', members: 0, since: '2026-10', country: 'Norway', mrr: 0 },
  { id: 9, name: 'Hamburg Kerala Samajam', plan: 'Community', status: 'live', members: 156, since: '2026-04', country: 'Germany', mrr: 199 },
]

export const photoLabels = ['Anjali, Durga Puja', 'Dhunuchi naach', 'Saraswati Puja', 'Cultural evening', 'Bhog', 'Alpona', 'Saturday school', 'Rabindra Jayanti', 'Committee 2026']

// Tenant site news (placeholders, English only)
export interface Article { id: string; kicker: string; title: string; excerpt: string; paragraphs: [string, string]; quote: string }
export const articles: Article[] = [
  { id: 'pujo-season', kicker: 'Festival', title: 'The Pujo season starts at dawn', excerpt: 'Mahalaya opens the festival on Saturday morning. Here is what to bring and where to park.', paragraphs: ['Mahalaya marks the start of the Pujo season. The recital begins at 05:30 at Furuset Forum, followed by tea and mishti for everyone who stays.', 'Doors open at 05:00. Bring a shawl: the hall is cool at that hour. Parking is free in the lot behind the building until 08:00.'], quote: 'We spent our time on the festival, not on the spreadsheet.' },
  { id: 'new-committee', kicker: 'Committee', title: 'Meet the committee for 2026', excerpt: 'Six volunteers take over the work from the annual meeting. A short introduction to each of them.', paragraphs: ['The annual meeting elected six people to the committee. Most have helped at festivals for years and know the hall, the caterers and the sound system better than anyone.', 'You can reach them through the contact form. Every message goes to the whole committee, so someone always answers.'], quote: 'Many hands make a festival.' },
  { id: 'school-term', kicker: 'Saturday school', title: 'Saturday school starts in January', excerpt: 'Registration for the spring term is open for children from five to twelve.', paragraphs: ['Lessons run on Saturday mornings in the same hall. Children learn the alphabet, songs and short plays that they perform at Saraswati Puja.', 'Registration is free for members. Places are limited to twenty children per group, so register early.'], quote: 'Learning together is half the fun.' },
]
