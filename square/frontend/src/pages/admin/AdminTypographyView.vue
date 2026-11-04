<script setup lang="ts">
import SettingsSectionNav from '../../components/SettingsSectionNav.vue'
import SettingsBackButton from '../../components/SettingsBackButton.vue'
import { ref, onMounted } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { fetchAdminSettings, updateAdminSettings, ValidationError } from '../../services/adminSettingsApi'
import type { DescriptionStyle } from '../../services/settingsApi'
import { useToast } from '../../composables/useToast'

const toast = useToast()

const loading = ref(true)
const saving = ref(false)
const error = ref(false)
const errors = ref<Record<string, string>>({})
const descriptionStyle = ref<DescriptionStyle>('karla')

// The three treatments from the Design System "Description Type" exploration. Sample styles are
// spelled out here (not via the global data-desc-style) so each option previews its own typeface.
const OPTIONS: { value: DescriptionStyle; label: string; sampleStyle: string }[] = [
  { value: 'karla', label: 'Karla (current)', sampleStyle: 'font-family: var(--ds-font-body); font-size: 16px; line-height: 1.6; color: var(--ds-text-body)' },
  { value: 'cormorant', label: 'Cormorant Garamond', sampleStyle: 'font-family: var(--ds-font-editorial); font-weight: 500; font-size: 19px; line-height: 1.5; color: var(--ds-text-heading)' },
  { value: 'source', label: 'Source Serif 4', sampleStyle: 'font-family: "Source Serif 4", Georgia, serif; font-size: 17px; line-height: 1.6; color: var(--ds-text-body)' },
]

async function load() {
  loading.value = true
  error.value = false
  try {
    descriptionStyle.value = (await fetchAdminSettings()).description_style ?? 'karla'
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  errors.value = {}
  try {
    const settings = await updateAdminSettings({ description_style: descriptionStyle.value })
    descriptionStyle.value = settings.description_style
    // Applies immediately in this tab; other visitors get it on their next page load.
    document.documentElement.dataset.descStyle = settings.description_style
    toast.success('Typography saved')
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
    } else {
      toast.error('Could not save typography')
    }
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Settings</h1>
        <p class="ds-intro">Site-wide settings and content that do not change often.</p>
      </div>
    </div>

    <SettingsSectionNav />

    <div style="width: 100%; max-width: 860px; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <h2 class="ds-display ds-display-s">Typography</h2>
        <SettingsBackButton />
      </div>

      <BaseLoadingState v-if="loading" label="Loading typography…" />
      <div v-else-if="error" class="ds-alert ds-alert-danger"><div>Couldn't load the typography settings. Please try again shortly.</div></div>
      <div v-else class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <div>
          <h3 class="ds-subtitle">Description style</h3>
          <p class="ds-meta" style="margin-top: var(--ds-space-1)">
            The typeface for descriptions across the site: event, news, gallery album and magazine text. An individual event can override it in its own form.
          </p>
        </div>
        <div role="radiogroup" aria-label="Description style" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr)); gap: var(--ds-space-3)">
          <label
            v-for="option in OPTIONS"
            :key="option.value"
            class="description-style-option"
            :class="{ 'description-style-option--selected': descriptionStyle === option.value }"
          >
            <input v-model="descriptionStyle" type="radio" name="description_style" :value="option.value" :aria-label="option.label" style="position: absolute; opacity: 0" />
            <span class="ds-eyebrow">{{ option.label }}</span>
            <span :style="option.sampleStyle">The last afternoon of the festival: goodbyes before the closingjan.</span>
          </label>
        </div>
        <span v-if="errors.description_style" class="ds-field-error-text">{{ errors.description_style }}</span>
        <BaseButton type="button" style="align-self: flex-start" :disabled="saving" @click="save">
          {{ saving ? 'Saving…' : 'Save' }}
        </BaseButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.description-style-option {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-2);
  padding: var(--ds-space-4);
  border: 1px solid var(--ds-border-hairline);
  border-radius: 12px;
  background: var(--ds-surface-card);
  cursor: pointer;
}
.description-style-option:hover {
  border-color: var(--ds-terracotta-300);
}
.description-style-option--selected {
  border-color: var(--ds-action-primary);
  box-shadow: 0 0 0 1px var(--ds-action-primary);
}
.description-style-option:focus-within {
  outline: 2px solid var(--ds-action-primary);
  outline-offset: 2px;
}
</style>
