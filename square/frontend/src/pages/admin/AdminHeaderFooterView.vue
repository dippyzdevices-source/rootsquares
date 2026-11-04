<script setup lang="ts">
import SettingsSectionNav from '../../components/SettingsSectionNav.vue'
import SettingsBackButton from '../../components/SettingsBackButton.vue'
import { onMounted } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import { useHomeContentForm } from '../../composables/useHomeContentForm'
import { SOCIAL_NETWORKS, type HomeContent } from '../../services/siteContent'

// The words and look of the top bar, header and footer (rootsquares W6-R74; moved here from the Home page settings). Every box is optional:
// an empty one shows nothing (or the neutral text).
const KEYS: (keyof HomeContent)[] = ['utility_text', 'tagline_local', 'logo_size', 'name_style', 'footer_registration', 'footer_blurb', 'footer_copyright', 'social_links']
const { loading, saving, error, form, social, load, save } = useHomeContentForm(KEYS, 'Header and footer saved')
onMounted(load)

const HEADER_FIELDS: { key: keyof HomeContent; label: string; hint: string; long?: boolean }[] = [
  { key: 'utility_text', label: 'Top bar text', hint: 'The small line at the very top of every page, for example "Est. 2010".' },
  { key: 'tagline_local', label: 'Line under the name', hint: 'Shown under the name in the header and footer, for example your name in your own language.' },
]
const FOOTER_FIELDS: { key: keyof HomeContent; label: string; hint: string; long?: boolean }[] = [
  { key: 'footer_registration', label: 'Registration line', hint: 'For example "Org. nr. 123456789". Empty shows nothing.' },
  { key: 'footer_blurb', label: 'Short description', hint: 'Shown under the name in the footer. Empty shows nothing.', long: true },
  { key: 'footer_copyright', label: 'Copyright line', hint: 'The whole line at the bottom of the footer. Empty shows "© year and your name".' },
]
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
        <h2 class="ds-display ds-display-s">Header &amp; footer</h2>
        <SettingsBackButton />
      </div>

      <BaseLoadingState v-if="loading" label="Loading header and footer…" />
      <div v-else class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <p class="ds-meta">What shows at the top and bottom of every page. Leave a box empty and that part is simply not shown. Your logos are set on the rootsquares platform, on your square's page.</p>

        <h3 class="ds-title">Header</h3>
        <label v-for="field in HEADER_FIELDS" :key="field.key" class="ds-field">
          <span class="ds-field-label">{{ field.label }}</span>
          <span class="ds-field-control"><input v-model="(form[field.key] as string)" type="text" class="ds-field-input" :aria-label="field.label" /></span>
          <span class="ds-meta">{{ field.hint }}</span>
        </label>
        <BaseSelect
          v-model="form.logo_size"
          label="Logo size"
          hint="How tall your logo is in the header and footer. It keeps its own shape, square, round or wide, and is never stretched."
          :options="[{ value: '', label: 'Medium (default)' }, { value: 'small', label: 'Small' }, { value: 'large', label: 'Large' }]"
        />
        <BaseSelect
          v-model="form.name_style"
          label="How the name is written"
          hint='In the header and footer, for example "MY·CLUB".'
          :options="[{ value: '', label: 'As written (default)' }, { value: 'caps', label: 'CAPITALS with a dot between the words' }]"
        />

        <h3 class="ds-title">Footer</h3>
        <label v-for="field in FOOTER_FIELDS" :key="field.key" class="ds-field">
          <span class="ds-field-label">{{ field.label }}</span>
          <span v-if="field.long" class="ds-textarea-control">
            <textarea v-model="(form[field.key] as string)" rows="3" class="ds-textarea" :aria-label="field.label"></textarea>
          </span>
          <span v-else class="ds-field-control"><input v-model="(form[field.key] as string)" type="text" class="ds-field-input" :aria-label="field.label" /></span>
          <span class="ds-meta">{{ field.hint }}</span>
        </label>
        <div>
          <span class="ds-field-label">Social links</span>
          <div v-for="network in SOCIAL_NETWORKS" :key="network" style="display: flex; gap: var(--ds-space-3); align-items: center; margin-top: var(--ds-space-2)">
            <span style="width: 90px; text-transform: capitalize">{{ network }}</span>
            <span class="ds-field-control" style="flex: 1"><input v-model="social[network]" type="url" class="ds-field-input" :aria-label="`${network} address`" placeholder="https://" /></span>
          </div>
          <span class="ds-meta">Only the ones you fill in are shown, as icons under "Follow us". Addresses start with https://.</span>
        </div>

        <span v-if="error" class="ds-field-error-text">{{ error }}</span>
        <BaseButton type="button" style="align-self: flex-start" :disabled="saving" @click="save">{{ saving ? 'Saving…' : 'Save' }}</BaseButton>
      </div>
    </div>
  </div>
</template>
