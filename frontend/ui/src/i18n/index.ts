import { createI18n } from 'vue-i18n'
import en from './en.json'
import no from './no.json'

export type Locale = 'en' | 'no'
export const LOCALES: Locale[] = ['en', 'no']

export const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: { en, no },
})
