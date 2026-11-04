// Suggestions that fit the kind of group a square is (W14-R10). They are only offered, never applied by themselves: the owner reads them, changes them and
// saves, so every word on the site is still the square's own (rule 11). English only (new texts go to en.json/English).
import { squareProfile } from './squareConfig'
import { moduleEnabled } from './modules'

export interface SuggestedReminder {
  name: string
  trigger: string
  offset_days: number
  send_hour: number
  subject: string
  body_html: string
}

export interface StarterSuggestions {
  donation_intro: string
  donation_thanks: string
  reminders: SuggestedReminder[]
}

const EVENT_BODY =
  '<p>Hello {{name}},</p><p>A reminder that <strong>{{event_title}}</strong> is on {{event_date}} at {{event_time}}, {{event_venue}}.</p><p>We look forward to seeing you.</p>'

const CULTURAL: StarterSuggestions = {
  donation_intro: 'Your gift helps us keep our events and traditions alive.',
  donation_thanks: 'Thank you for your generous gift. It makes our work possible.',
  reminders: [
    { name: 'The day before an event (ticket holders)', trigger: 'event_before', offset_days: 1, send_hour: 9, subject: 'Tomorrow: {{event_title}}', body_html: EVENT_BODY },
    {
      name: 'Two weeks before a membership ends',
      trigger: 'membership_ending',
      offset_days: 14,
      send_hour: 9,
      subject: 'Your membership ends on {{end_date}}',
      body_html: '<p>Hello {{name}},</p><p>Your {{membership_type}} membership ends on {{end_date}}. Thank you for being part of us.</p>',
    },
  ],
}

const RELIGIOUS: StarterSuggestions = {
  donation_intro: 'Your gifts support our gatherings, our community and the people who need us.',
  donation_thanks: 'Thank you for your generosity. Your gift supports our community.',
  reminders: [
    { name: 'The day before a gathering (everyone on the member list)', trigger: 'event_before_members', offset_days: 1, send_hour: 9, subject: 'Tomorrow: {{event_title}}', body_html: EVENT_BODY },
  ],
}

const BAND: StarterSuggestions = {
  donation_intro: 'Your support helps us write, record and play more music.',
  donation_thanks: 'Thank you for your support. It keeps the music going.',
  reminders: [
    { name: 'The day before a gig (ticket holders)', trigger: 'event_before', offset_days: 1, send_hour: 9, subject: 'Tomorrow: {{event_title}}', body_html: EVENT_BODY },
  ],
}

const CHARITY: StarterSuggestions = {
  donation_intro: 'Your gift helps us reach the people who need us most.',
  donation_thanks: 'Thank you for your generosity. Every gift makes a difference.',
  reminders: [
    { name: 'The day before an event (ticket holders)', trigger: 'event_before', offset_days: 1, send_hour: 9, subject: 'Tomorrow: {{event_title}}', body_html: EVENT_BODY },
  ],
}

const BY_GROUP: Record<string, StarterSuggestions> = { cultural: CULTURAL, religious: RELIGIOUS, band: BAND, charity: CHARITY }

/** The suggestions for the square's kind of group; a square made before starter sets gets the cultural ones, the default of the platform. */
export function suggestionsFor(groupType: string = squareProfile.groupType): StarterSuggestions {
  return BY_GROUP[groupType] ?? CULTURAL
}

const TRIGGER_MODULES: Record<string, string[]> = {
  event_before: ['events', 'tickets'],
  event_before_members: ['events', 'members'],
  membership_ending: ['memberships'],
  period_due: ['memberships'],
}

/** Only the reminders whose modules are on in this square. */
export function availableReminderSuggestions(groupType?: string): SuggestedReminder[] {
  return suggestionsFor(groupType).reminders.filter((r) => (TRIGGER_MODULES[r.trigger] ?? []).every((m) => moduleEnabled(m as Parameters<typeof moduleEnabled>[0])))
}

/** The kind of group in words, or '' when unknown. */
export function groupLabel(groupType: string = squareProfile.groupType): string {
  return { religious: 'religious community', cultural: 'cultural group', band: 'band or artist', charity: 'charity or fundraiser' }[groupType] ?? ''
}
