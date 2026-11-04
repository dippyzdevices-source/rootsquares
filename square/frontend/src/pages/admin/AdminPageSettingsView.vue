<script setup lang="ts">
import SettingsSectionNav from '../../components/SettingsSectionNav.vue'
import SettingsBackButton from '../../components/SettingsBackButton.vue'
import { computed, onMounted, watch } from 'vue'
import { moduleEnabled, type ModuleKey } from '../../services/modules'
import HeritageMediaCards from '../../components/HeritageMediaCards.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { useHomeContentForm } from '../../composables/useHomeContentForm'
import type { AboutPage, GalleryBand, HomeContent, NewsBand, PageHeading, PageKey } from '../../services/siteContent'

// One admin page per public page (Settings, Pages & media; W8-R4): the heading block of the page and every other word of it. The heading block is: a small line, a handwritten line, the title, the title in the community's own language, and an intro
// (rootsquares W6-R75). Every box is optional: an empty one keeps the page's neutral text (the handwritten and own-language lines show only when set).
const KEYS: (keyof HomeContent)[] = ['page_headings', 'gallery_band', 'news_band', 'contact_page', 'about_page', 'membership_page']
const props = defineProps<{ page: string }>()
const { loading, saving, error, form, load, save } = useHomeContentForm(KEYS, 'Page saved')
onMounted(load)
watch(() => props.page, load)

const PAGES: { key: PageKey; label: string; where: string }[] = [
  { key: 'events', label: 'Events', where: 'The list of events' },
  { key: 'gallery', label: 'Gallery', where: 'The photo gallery' },
  { key: 'news', label: 'News', where: 'News and notices' },
  { key: 'membership', label: 'Membership', where: 'The "Become a member" page' },
  { key: 'contact', label: 'Contact', where: 'The contact page' },
  { key: 'committee', label: 'Committee', where: 'The committee page' },
  { key: 'heritage', label: 'About', where: 'The About page' },
]
const PAGE_ROUTES: Record<string, PageKey> = { events: 'events', gallery: 'gallery', news: 'news', newsletter: 'news', membership: 'membership', contact: 'contact', committee: 'committee', about: 'heritage' }
// 'newsletter' = the sign-up words only (the same band as under the news list, for a square that has the newsletter but no news; W14-R13)
const bandOnly = computed(() => props.page === 'newsletter')
const current = computed(() => {
  const key = PAGE_ROUTES[props.page]
  if (bandOnly.value) return { key: 'news' as PageKey, label: 'Newsletter sign-up', where: 'The newsletter sign-up page and the band under the news list' }
  return key ? PAGES.find((p) => p.key === key) : undefined
})
const FIELDS: { key: keyof PageHeading; label: string; long?: boolean }[] = [
  { key: 'nav_label', label: 'Name in the menu, footer and browser tab' },
  { key: 'eyebrow', label: 'Small line above the title' },
  { key: 'script_line', label: 'Handwritten line' },
  { key: 'title', label: 'Title' },
  { key: 'local_line', label: 'Title in your own language' },
  { key: 'intro', label: 'Intro', long: true },
]
// The band at the bottom of the gallery page (W7-R4). No title = no band, no button label = no button, the coverage list is off unless ticked.
const BAND_FIELDS: { key: Exclude<keyof GalleryBand, 'show_coverage'>; label: string; long?: boolean }[] = [
  { key: 'eyebrow', label: 'Small line above the title' },
  { key: 'title', label: 'Title' },
  { key: 'text', label: 'Text', long: true },
  { key: 'button_label', label: 'Button label (opens your contact page)' },
]
// The newsletter band at the bottom of the news page (W7-R5). No title = no band and no subscribe form. (The Magazines tab is the Magazines module since W8-R14.)
const NEWS_BAND_FIELDS: { key: Exclude<keyof NewsBand, 'show_magazines'>; label: string; long?: boolean }[] = [
  { key: 'eyebrow', label: 'Small line above the title' },
  { key: 'title', label: 'Title' },
  { key: 'text', label: 'Text', long: true },
  { key: 'consent', label: 'Line under the sign-up field (what subscribing means)', long: true },
]
// The questions under the contact form and the line under the page (W7-R9). No question = no section; empty footnote = no line.
const ALL_CONTACT_FIELDS: { key: 'faq_eyebrow' | 'faq_title' | 'footnote_text' | 'footnote_link'; label: string; module?: ModuleKey }[] = [
  { key: 'faq_eyebrow', label: 'Small line above the questions' },
  { key: 'faq_title', label: 'Heading above the questions' },
  { key: 'footnote_text', label: 'Line under the page (before the link)' },
  { key: 'footnote_link', label: 'Link text to the membership page', module: 'memberships' },
]
// The sections of the About page (W7-R10). Each shows only when it has words or rows; founders come from Content, Founders.
// A box that points at the membership page is not offered without the Memberships module (W8-R19).
const ALL_ABOUT_GROUPS: { title: string; hint: string; fields: { key: keyof Omit<AboutPage, 'values' | 'timeline'>; label: string; long?: boolean; module?: ModuleKey }[] }[] = [
  {
    title: 'Who are we',
    hint: 'Cards about what the association stands for (below). The title and the button to the committee page are optional.',
    fields: [
      { key: 'values_title', label: 'Title' },
      { key: 'values_button', label: 'Button to the committee page', module: 'committee' },
    ],
  },
  {
    title: 'What we do',
    hint: 'A short text, with optional links to your membership and events pages.',
    fields: [
      { key: 'what_title', label: 'Title' },
      { key: 'what_text', label: 'Text', long: true },
      { key: 'what_membership_link', label: 'Link text to the membership page', module: 'memberships' },
      { key: 'what_events_link', label: 'Link text to the events page' },
    ],
  },
]
const CONTACT_FIELDS = ALL_CONTACT_FIELDS.filter((field) => moduleEnabled(field.module))
// A box that points at a module the owner turned off is not offered (W8-R12).
const ABOUT_GROUPS = ALL_ABOUT_GROUPS.map((group) => ({ ...group, fields: group.fields.filter((field) => moduleEnabled(field.module)) }))
const foundersOn = moduleEnabled('founders')
const ABOUT_TIMELINE_FIELDS: { key: keyof Omit<AboutPage, 'values' | 'timeline'>; label: string }[] = [
  { key: 'timeline_eyebrow', label: 'Small line above the timeline' },
  { key: 'timeline_title', label: 'Title' },
]
const ABOUT_INVOLVE_FIELDS: { key: keyof Omit<AboutPage, 'values' | 'timeline'>; label: string; long?: boolean }[] = [
  { key: 'involve_badge', label: 'Small label' },
  { key: 'involve_title', label: 'Title' },
  { key: 'involve_text', label: 'Text', long: true },
  { key: 'involve_button', label: 'Button to the contact page' },
]
const value = (page: PageKey, field: keyof PageHeading) => (form.value.page_headings[page] as Record<string, string>)[field]
const setValue = (page: PageKey, field: keyof PageHeading, text: string) => {
  ;(form.value.page_headings[page] as Record<string, string>)[field] = text
}
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div class="ds-heading">
      <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
      <h1 class="ds-display ds-display-s">Settings</h1>
      <p class="ds-intro">Site-wide settings and content that do not change often.</p>
    </div>

    <SettingsSectionNav />

    <div v-if="!current" style="max-width: 760px">
      <h2 class="ds-display ds-display-s">Page not found</h2>
      <p class="ds-meta">There is no page called "{{ page }}" to set up.</p>
    </div>
    <div v-else style="max-width: 760px; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <h2 class="ds-display ds-display-s">{{ current.label }}</h2>
        <SettingsBackButton />
      </div>

      <BaseLoadingState v-if="loading" label="Loading the page…" />
      <template v-else>
        <p v-if="!bandOnly" class="ds-meta">{{ current.where }}. Leave a box empty to keep the page's own text. The handwritten line and the title in your own language show only if you fill them in.</p>

        <div v-if="!bandOnly" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <div>
            <h3 class="ds-title">Heading</h3>
            <p class="ds-meta">The words at the top of the page.</p>
          </div>
          <label v-for="field in FIELDS" :key="field.key" class="ds-field">
            <span class="ds-field-label">{{ field.label }}</span>
            <span v-if="field.long" class="ds-textarea-control">
              <textarea :value="value(current.key, field.key)" rows="2" class="ds-textarea" :aria-label="`${current.label}: ${field.label}`" @input="setValue(current.key, field.key, ($event.target as HTMLTextAreaElement).value)"></textarea>
            </span>
            <span v-else class="ds-field-control"><input :value="value(current.key, field.key)" type="text" class="ds-field-input" :aria-label="`${current.label}: ${field.label}`" @input="setValue(current.key, field.key, ($event.target as HTMLInputElement).value)" /></span>
          </label>
        </div>

        <div v-if="page === 'gallery'" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <div>
            <h3 class="ds-title">Gallery: band at the bottom</h3>
            <p class="ds-meta">A call to action under the albums, for example to ask for old photographs. Leave the title empty and no band is shown.</p>
          </div>
          <label v-for="field in BAND_FIELDS" :key="field.key" class="ds-field">
            <span class="ds-field-label">{{ field.label }}</span>
            <span v-if="field.long" class="ds-textarea-control">
              <textarea v-model="form.gallery_band[field.key]" rows="2" class="ds-textarea" :aria-label="`Gallery band: ${field.label}`"></textarea>
            </span>
            <span v-else class="ds-field-control"><input v-model="form.gallery_band[field.key]" type="text" class="ds-field-input" :aria-label="`Gallery band: ${field.label}`" /></span>
          </label>
          <label style="display: flex; align-items: center; gap: var(--ds-space-2)">
            <input v-model="form.gallery_band.show_coverage" type="checkbox" aria-label="Gallery band: show which years have photos" />
            <span>Also list which five-year periods have photos (from the albums' years)</span>
          </label>
        </div>

        <div v-if="(page === 'news' || bandOnly) && moduleEnabled('newsletter')" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <div>
            <h3 class="ds-title">News: newsletter band</h3>
            <p class="ds-meta">A newsletter sign-up under the news list. Leave the title empty and no band or sign-up form is shown.</p>
          </div>
          <label v-for="field in NEWS_BAND_FIELDS" :key="field.key" class="ds-field">
            <span class="ds-field-label">{{ field.label }}</span>
            <span v-if="field.long" class="ds-textarea-control">
              <textarea v-model="form.news_band[field.key]" rows="2" class="ds-textarea" :aria-label="`News band: ${field.label}`"></textarea>
            </span>
            <span v-else class="ds-field-control"><input v-model="form.news_band[field.key]" type="text" class="ds-field-input" :aria-label="`News band: ${field.label}`" /></span>
          </label>
        </div>

        <div v-if="page === 'contact'" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <div>
            <h3 class="ds-title">Contact: questions and footnote</h3>
            <p class="ds-meta">Common questions under the contact form (up to five; a row needs a question and an answer), and a line under the page with a link to your membership page. Leave them empty and nothing is shown. The reasons people can pick in the form are a list under Settings, Lists, Contact reasons.</p>
          </div>
          <label v-for="field in CONTACT_FIELDS" :key="field.key" class="ds-field">
            <span class="ds-field-label">{{ field.label }}</span>
            <span class="ds-field-control"><input v-model="form.contact_page[field.key]" type="text" class="ds-field-input" :aria-label="`Contact: ${field.label}`" /></span>
          </label>
          <div v-for="(item, index) in form.contact_page.faq" :key="index" style="display: flex; flex-direction: column; gap: var(--ds-space-2)">
            <span class="ds-field-control"><input v-model="item.title" type="text" class="ds-field-input" :aria-label="`Question ${index + 1}`" placeholder="Question" /></span>
            <span class="ds-textarea-control"><textarea v-model="item.content" rows="2" class="ds-textarea" :aria-label="`Answer ${index + 1}`" placeholder="Answer"></textarea></span>
          </div>
        </div>

        <div v-if="page === 'about'" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <div>
            <h3 class="ds-title">About: sections</h3>
            <p class="ds-meta">The sections under the About text. Each shows only when it has something in it.<template v-if="foundersOn"> The founders' quotes come from Settings, People, Founders: with none added, that part is not shown.</template> The photo and the story text are the two cards below.</p>
          </div>
          <template v-for="group in ABOUT_GROUPS" :key="group.title">
            <h4 class="ds-subtitle">{{ group.title }}</h4>
            <p v-if="group.title === 'Who are we'" class="ds-meta">{{ group.hint }}</p>
            <label v-for="field in group.fields" :key="field.key" class="ds-field">
              <span class="ds-field-label">{{ field.label }}</span>
              <span v-if="field.long" class="ds-textarea-control"><textarea v-model="(form.about_page[field.key] as string)" rows="3" class="ds-textarea" :aria-label="`About ${group.title}: ${field.label}`"></textarea></span>
              <span v-else class="ds-field-control"><input v-model="(form.about_page[field.key] as string)" type="text" class="ds-field-input" :aria-label="`About ${group.title}: ${field.label}`" /></span>
            </label>
            <template v-if="group.title === 'Who are we'">
              <div v-for="(item, index) in form.about_page.values" :key="index" style="display: flex; flex-direction: column; gap: var(--ds-space-2)">
                <span class="ds-field-control"><input v-model="item.title" type="text" class="ds-field-input" :aria-label="`Card ${index + 1} title`" placeholder="Card title" /></span>
                <span class="ds-textarea-control"><textarea v-model="item.description" rows="2" class="ds-textarea" :aria-label="`Card ${index + 1} text`" placeholder="Card text"></textarea></span>
              </div>
            </template>
          </template>
          <h4 class="ds-subtitle">Timeline</h4>
          <p class="ds-meta">Up to ten rows; a row needs a title.</p>
          <label v-for="field in ABOUT_TIMELINE_FIELDS" :key="field.key" class="ds-field">
            <span class="ds-field-label">{{ field.label }}</span>
            <span class="ds-field-control"><input v-model="(form.about_page[field.key] as string)" type="text" class="ds-field-input" :aria-label="`About timeline: ${field.label}`" /></span>
          </label>
          <div v-for="(row, index) in form.about_page.timeline" :key="index" style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap">
            <span class="ds-field-control" style="width: 90px"><input v-model="row.year" type="text" maxlength="12" class="ds-field-input" :aria-label="`Timeline ${index + 1} year`" placeholder="Year" /></span>
            <span class="ds-field-control" style="flex: 1; min-width: 160px"><input v-model="row.title" type="text" class="ds-field-input" :aria-label="`Timeline ${index + 1} title`" placeholder="Title" /></span>
            <span class="ds-field-control" style="flex: 2; min-width: 200px"><input v-model="row.description" type="text" class="ds-field-input" :aria-label="`Timeline ${index + 1} text`" placeholder="Text" /></span>
          </div>
          <h4 class="ds-subtitle">Get involved</h4>
          <label v-for="field in ABOUT_INVOLVE_FIELDS" :key="field.key" class="ds-field">
            <span class="ds-field-label">{{ field.label }}</span>
            <span v-if="field.long" class="ds-textarea-control"><textarea v-model="(form.about_page[field.key] as string)" rows="3" class="ds-textarea" :aria-label="`About get involved: ${field.label}`"></textarea></span>
            <span v-else class="ds-field-control"><input v-model="(form.about_page[field.key] as string)" type="text" class="ds-field-input" :aria-label="`About get involved: ${field.label}`" /></span>
          </label>
        </div>

        <div v-if="page === 'membership'" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <div>
            <h3 class="ds-title">Membership: why join and how to join</h3>
            <p class="ds-meta">Two short lists next to the membership types (up to six lines each). A list with no lines is not shown. The membership types and prices are under Memberships in the admin menu.</p>
          </div>
          <label class="ds-field">
            <span class="ds-field-label">Small line above the reasons</span>
            <span class="ds-field-control"><input v-model="form.membership_page.benefits_eyebrow" type="text" class="ds-field-input" aria-label="Membership: small line above the reasons" /></span>
          </label>
          <span v-for="(item, index) in form.membership_page.benefits" :key="`b${index}`" class="ds-field-control"><input v-model="item.text" type="text" class="ds-field-input" :aria-label="`Reason ${index + 1}`" placeholder="A reason to join" /></span>
          <label class="ds-field">
            <span class="ds-field-label">Small line above the steps</span>
            <span class="ds-field-control"><input v-model="form.membership_page.steps_eyebrow" type="text" class="ds-field-input" aria-label="Membership: small line above the steps" /></span>
          </label>
          <span v-for="(item, index) in form.membership_page.steps" :key="`s${index}`" class="ds-field-control"><input v-model="item.text" type="text" class="ds-field-input" :aria-label="`Step ${index + 1}`" placeholder="A step to join, in order" /></span>
        </div>

        <span v-if="error" class="ds-field-error-text">{{ error }}</span>
        <BaseButton type="button" style="align-self: flex-start" :disabled="saving" @click="save">{{ saving ? 'Saving…' : 'Save' }}</BaseButton>
      </template>

      <template v-if="page === 'about'">
        <h3 class="ds-display ds-display-s">Photo and story text</h3>
        <p class="ds-meta">These two cards have their own Save buttons.</p>
        <HeritageMediaCards />
      </template>
    </div>
  </div>
</template>
