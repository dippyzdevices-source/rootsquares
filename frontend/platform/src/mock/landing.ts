// MOCK DATA for the landing page. Nothing here is real: names, events, prices and the BCA numbers are placeholders.

import { CASE_FIGURES } from './placeholders'


export const LAUNCH_THEMES = ['paper-brick'] as const // only enabled themes (src/themes/index.ts)

export const MOCK_EVENTS = [
  { day: '12', month: 'Nov', title: 'Winter concert', meta: '86 / 120 tickets' },
  { day: '28', month: 'Nov', title: 'Lucia evening', meta: '41 / 80 tickets' },
  { day: '19', month: 'Jan', title: 'Annual meeting', meta: '23 / 60 tickets' },
]

export const MODULE_IDS = ['events', 'tickets', 'membership', 'committee', 'gallery', 'accounting', 'domain'] as const
export type ModuleId = (typeof MODULE_IDS)[number]

export const PREVIEW = {
  events: [
    { date: '12 Nov', title: 'Winter concert', meta: 'Main hall · 86 / 120', status: 'live' },
    { date: '28 Nov', title: 'Lucia evening', meta: 'Church hall · 41 / 80', status: 'live' },
    { date: '14 Dec', title: 'Christmas market', meta: 'Not on sale', status: 'draft' },
  ],
  tickets: [
    { name: 'Adult', price: 'NOK 320', qty: '58 sold' },
    { name: 'Child under 12', price: 'NOK 0', qty: '12 sold' },
    { name: 'Family of four', price: 'NOK 960', qty: '9 sold' },
  ],
  orders: [
    { who: 'Ola Nordmann', ref: '#1052', status: 'pending', total: 'NOK 640' },
    { who: 'Siv Aasen', ref: '#1050', status: 'paid', total: 'NOK 960' },
  ],
  members: [
    { name: 'Siv Aasen', kind: 'Family', status: 'paid' },
    { name: 'Per Dahl', kind: 'Full member', status: 'paid' },
    { name: 'Marit Solberg', kind: 'Student', status: 'overdue' },
  ],
  committee: [
    { ini: 'IH', name: 'Ingrid Haugen', role: 'Chair' },
    { ini: 'TL', name: 'Tor Lund', role: 'Treasurer' },
    { ini: 'EH', name: 'Elin Haugen', role: 'Secretary' },
  ],
  gallery: ['Winter concert', 'Lucia procession', 'Market stalls', 'Choir', 'Workshop', 'Annual meeting'],
  article: { date: '02 Oct', title: 'A new season begins', meta: 'News · 2 min read' },
  ledger: [
    { what: 'Ticket sales: Winter concert', amount: '+ 12 600' },
    { what: 'Hall rental', amount: '− 4 000' },
    { what: 'Membership fees (14)', amount: '+ 5 600' },
  ],
}

// MOCK proof strip (BCA Oslo). Invented figures, not measured.
export const BCA_STATS = [
  { id: 'launch', value: CASE_FIGURES.launchMinutes + ' min' },
  { id: 'members', value: String(CASE_FIGURES.members) },
  { id: 'festivals', value: String(CASE_FIGURES.festivals) },
  { id: 'sheets', value: String(CASE_FIGURES.spreadsheets) },
]
