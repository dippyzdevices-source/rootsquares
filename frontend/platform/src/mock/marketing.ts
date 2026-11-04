// Mock data. Plan names, prices and feature lists are the placeholders from design/ui_kits/marketing/Site.jsx.
export interface Plan {
  id: 'small' | 'community' | 'federation'
  features: number // count of i18n keys f1..fN
  highlighted?: boolean
}

export const plans: Plan[] = [
  { id: 'small', features: 4 },
  { id: 'community', features: 5, highlighted: true },
  { id: 'federation', features: 5 },
]

export const features = [
  { id: 'events', icon: 'calendar' },
  { id: 'tickets', icon: 'ticket' },
  { id: 'membership', icon: 'users' },
  { id: 'gallery', icon: 'image' },
  { id: 'accounting', icon: 'chart' },
  { id: 'domain', icon: 'globe' },
] as const

export const faqIds = ['1', '2', '3', '4'] as const

import { CASE_FIGURES } from './placeholders'

export interface CaseStat { id: string; value: string }
export const caseStats: CaseStat[] = [
  { id: 'launch', value: CASE_FIGURES.launchMinutes + ' min' },
  { id: 'members', value: String(CASE_FIGURES.members) },
  { id: 'events', value: String(CASE_FIGURES.festivals) },
  { id: 'sheets', value: String(CASE_FIGURES.spreadsheets) },
]

export const associationTypes = ['cultural', 'religious', 'language', 'other'] as const
