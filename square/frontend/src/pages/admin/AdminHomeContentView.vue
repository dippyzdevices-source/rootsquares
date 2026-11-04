<script setup lang="ts">
import { moduleEnabled } from '../../services/modules'
import SettingsSectionNav from '../../components/SettingsSectionNav.vue'
import SettingsBackButton from '../../components/SettingsBackButton.vue'
import { onMounted } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { useHomeContentForm } from '../../composables/useHomeContentForm'
import type { HomeContent } from '../../services/siteContent'

// The square's own words on its home page (rootsquares W6-R64; the header and footer words moved to their own page in W6-R74). Every box is
// optional: an empty one shows neutral text.
const KEYS: (keyof HomeContent)[] = ['eyebrow', 'script_line', 'headline', 'local_line', 'intro', 'intro_name', 'intro_suffix', 'stats', 'blurb', 'sponsors_eyebrow', 'sponsors_title', 'testimonials_eyebrow', 'testimonials_empty_text', 'testimonials_button', 'association_eyebrow', 'association_button']
const { loading, saving, error, form, load, save } = useHomeContentForm(KEYS, 'Home page content saved')
onMounted(load)

const TEXT_FIELDS: { key: keyof HomeContent; label: string; hint: string; long?: boolean }[] = [
  { key: 'eyebrow', label: 'Small line above the headline', hint: 'For example "Community · culture · celebration".' },
  { key: 'script_line', label: 'Handwritten line', hint: 'Shown above the headline in a handwriting font, for example "since 2010".' },
  { key: 'headline', label: 'Headline', hint: 'Empty shows the name of your square.' },
  { key: 'local_line', label: 'Headline in your own language', hint: 'Shown under the headline.' },
  { key: 'intro', label: 'Introduction', hint: 'A few sentences under the headline.', long: true },
  { key: 'intro_name', label: 'Full name of the association', hint: 'Shown large, in the handwriting font, under the introduction.' },
  { key: 'intro_suffix', label: 'Text after the full name', hint: 'For example "of Springfield."' },
  { key: 'blurb', label: 'Text in the dark "association" band', hint: 'Lower on the home page, next to the "Read our story" button.', long: true },
  { key: 'sponsors_eyebrow', label: 'Small line above the sponsors', hint: 'For example "Our sponsors". Sponsors are added under Content, Sponsors; with none, nothing is shown.' },
  { key: 'sponsors_title', label: 'Heading above the sponsors', hint: 'For example "With thanks to". Empty = no heading, only the logos.' },
  { key: 'testimonials_eyebrow', label: 'Small line above the testimonial', hint: 'For example "What our members say". Testimonials are added under Content, Testimonials.' },
  { key: 'testimonials_empty_text', label: 'Text while there are no testimonials', hint: 'For example "Be one of the first to share your story". Empty = the testimonial side stays hidden until there is one.', long: true },
  { key: 'testimonials_button', label: 'Button to send a testimonial', hint: 'For example "Share your story". Empty = no button.' },
  { key: 'association_eyebrow', label: 'Small line above the association text', hint: 'The text itself is the one in the dark "association" band above.' },
  { key: 'association_button', label: 'Button to the About page', hint: 'For example "Read our story". Empty = no button.' },
]
// The words of a part that belongs to a module the owner turned off are not offered (W8-R10).
const textFields = TEXT_FIELDS.filter((field) => moduleEnabled(field.key.startsWith('testimonials_') ? 'testimonials' : field.key.startsWith('sponsors_') ? 'sponsors' : undefined))
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div class="ds-heading">
      <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
      <h1 class="ds-display ds-display-s">Settings</h1>
      <p class="ds-intro">Site-wide settings and content that do not change often.</p>
    </div>

    <SettingsSectionNav />

    <div style="max-width: 760px; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <h2 class="ds-display ds-display-s">Home page</h2>
        <SettingsBackButton />
      </div>

      <BaseLoadingState v-if="loading" label="Loading home page content…" />
      <div v-else class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <p class="ds-meta">Your own words for the home page. Leave a box empty to show the neutral text. The top bar, header and footer are on the Header &amp; footer page.</p>

        <label v-for="field in textFields" :key="field.key" class="ds-field">
          <span class="ds-field-label">{{ field.label }}</span>
          <span v-if="field.long" class="ds-textarea-control">
            <textarea v-model="(form[field.key] as string)" rows="4" class="ds-textarea" :aria-label="field.label"></textarea>
          </span>
          <span v-else class="ds-field-control"><input v-model="(form[field.key] as string)" type="text" class="ds-field-input" :aria-label="field.label" /></span>
          <span class="ds-meta">{{ field.hint }}</span>
        </label>

        <div>
          <span class="ds-field-label">Numbers under the buttons (up to three)</span>
          <div v-for="(stat, index) in form.stats" :key="index" style="display: flex; gap: var(--ds-space-3); margin-top: var(--ds-space-2)">
            <span class="ds-field-control" style="width: 110px"><input v-model="stat.value" type="text" maxlength="12" class="ds-field-input" :aria-label="`Number ${index + 1}`" placeholder="16" /></span>
            <span class="ds-field-control" style="flex: 1"><input v-model="stat.label" type="text" maxlength="40" class="ds-field-input" :aria-label="`Label ${index + 1}`" placeholder="years together" /></span>
          </div>
          <span class="ds-meta">A row needs both a number and a label to show.</span>
        </div>

        <span v-if="error" class="ds-field-error-text">{{ error }}</span>
        <BaseButton type="button" style="align-self: flex-start" :disabled="saving" @click="save">{{ saving ? 'Saving…' : 'Save' }}</BaseButton>
      </div>
    </div>
  </div>
</template>
