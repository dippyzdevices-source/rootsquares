<script setup lang="ts">
import { moduleEnabled, type ModuleKey } from '../../services/modules'
import SettingsSectionNav from '../../components/SettingsSectionNav.vue'
import SettingsBackButton from '../../components/SettingsBackButton.vue'
import { ref, onMounted } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import {
  fetchAdminSettings,
  updateAdminSettings,
  ValidationError,
} from '../../services/adminSettingsApi'
import { useToast } from '../../composables/useToast'

const toast = useToast()

const loading = ref(true)
const saving = ref(false)
const errors = ref<Record<string, string>>({})
const form = ref({
  contact_email: '',
  contact_phone: '',
  contact_address: '',
  maintenance_mode: false,
  maintenance_allowed_event_slugs: '',
  maintenance_allowed_page_paths: '',
  maintenance_hidden_page_paths: '',
})

// Fixed set of the app's own top-level public pages — must match MAINTENANCE_PAGE_KEYS in
// backend/app/settings/admin_routes.py and MAINTENANCE_PAGE_KEY_PATHS in router/index.ts.
const EVENTS_PAGE = {
  key: 'events',
  label: 'Events list',
  hint: 'the listing only — individual event pages use their own Draft/Published setting and the allowed event slugs above',
}
const ALL_OTHER_PAGES: { key: string; label: string; module?: ModuleKey }[] = [
  { key: 'home', label: 'Home' },
  { key: 'heritage', label: 'About' },
  { key: 'committee', label: 'Committee', module: 'committee' },
  { key: 'gallery', label: 'Gallery', module: 'gallery' },
  { key: 'membership', label: 'Membership', module: 'memberships' },
  { key: 'news', label: 'News', module: 'news' },
  { key: 'contact', label: 'Contact' },
  { key: 'testimonials', label: 'Testimonials', module: 'testimonials' },
]
// A page of a module the owner turned off is not listed (W8-R10).
const OTHER_PAGES = ALL_OTHER_PAGES.filter((page) => moduleEnabled(page.module))

// Two comma-separated key lists give three states per page while the site is under
// construction: hidden (maintenance_hidden_page_paths — off for everyone, admins included),
// Published (maintenance_allowed_page_paths — everyone sees it), and otherwise admin-only.
function keysOf(value: string | undefined): string[] {
  return (value ?? '').split(',').map((key) => key.trim()).filter(Boolean)
}

function isVisible(key: string): boolean {
  return !keysOf(form.value.maintenance_hidden_page_paths).includes(key)
}

function isPublished(key: string): boolean {
  return keysOf(form.value.maintenance_allowed_page_paths).includes(key)
}

function setVisible(key: string, visible: boolean) {
  const current = new Set(keysOf(form.value.maintenance_hidden_page_paths))
  if (visible) current.delete(key)
  else current.add(key)
  form.value.maintenance_hidden_page_paths = Array.from(current).join(',')
}

function setPublished(key: string, published: boolean) {
  const current = new Set(keysOf(form.value.maintenance_allowed_page_paths))
  if (published) current.add(key)
  else current.delete(key)
  form.value.maintenance_allowed_page_paths = Array.from(current).join(',')
}

async function load() {
  loading.value = true
  const settings = await fetchAdminSettings()
  form.value = { ...settings }
  loading.value = false
}

async function save() {
  saving.value = true
  errors.value = {}
  try {
    const settings = await updateAdminSettings({
      maintenance_mode: form.value.maintenance_mode,
      maintenance_allowed_event_slugs: form.value.maintenance_allowed_event_slugs,
      maintenance_allowed_page_paths: form.value.maintenance_allowed_page_paths,
      maintenance_hidden_page_paths: form.value.maintenance_hidden_page_paths,
    })
    form.value = { ...settings }
    toast.success('Settings saved')
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
    } else {
      toast.error('Could not save settings')
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

    <div style="width: 100%; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <h2 class="ds-display ds-display-s">Site availability</h2>
        <SettingsBackButton />
      </div>

      <BaseLoadingState v-if="loading" label="Loading settings…" />
      <div v-else class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <div>
          <h2 class="ds-title">Site availability</h2>
          <p class="ds-meta">
            While the rest of the site is being finished, this keeps the public site limited
            to the one live event and its ticket flow (plus this admin console). Takes effect
            immediately for every visitor — no rebuild or redeploy needed.
          </p>
        </div>

        <label class="ds-switch" style="align-items: flex-start">
          <input v-model="form.maintenance_mode" type="checkbox" aria-label="Site under construction" />
          <span class="ds-switch-track"><span class="ds-switch-thumb"></span></span>
          <span>
            <span class="ds-switch-label" style="display: block">Site under construction</span>
            <span class="ds-checkbox-desc" style="display: block; margin-top: var(--ds-space-1)">While on, only the live event, its tickets, Published pages and this admin console are public; Admin pages are visible to signed-in admins only.</span>
          </span>
        </label>
        <span v-if="errors.maintenance_mode" class="ds-field-error-text">{{ errors.maintenance_mode }}</span>

        <div v-if="!form.maintenance_mode" class="ds-alert ds-alert-success site-live-notice" role="status">
          <div>
            <strong>The site is live.</strong> Every page is public, so the page settings that would normally appear here
            (allowed events, Visible / Published for each page) do not apply. They are kept as they are and come back the
            next time you switch "Site under construction" on.
          </div>
        </div>

        <template v-else>
        <div class="ds-field">
          <span class="ds-meta">
            Each page has two switches. <strong>Visible</strong> off switches the page off for
            everyone, admins included. With Visible on, <strong>Published</strong> off keeps it for signed-in admins only
            (with a preview banner) and Published on shows it to everyone.
          </span>
        </div>

        <div v-if="moduleEnabled('events')" class="ds-field" style="gap: var(--ds-space-4); margin-top: var(--ds-space-4)">
          <span class="ds-field-label">Events</span>
          <label class="ds-field">
            <span class="ds-field-label">Allowed event slugs</span>
            <span class="ds-field-control">
              <input v-model="form.maintenance_allowed_event_slugs" type="text" class="ds-field-input" placeholder="e.g. summer-festival-2026, spring-concert-2027" />
            </span>
            <span class="ds-meta">The event page(s) (their URL slugs, comma-separated) that stay public while the toggle above is on. Leave blank to allow none.</span>
            <span v-if="errors.maintenance_allowed_event_slugs" class="ds-field-error-text">{{ errors.maintenance_allowed_event_slugs }}</span>
          </label>
            <div class="page-visibility-row" :data-page="EVENTS_PAGE.key" style="width: 100%; display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-5); flex-wrap: wrap; padding: var(--ds-space-4) 0; border-top: 1px solid var(--ds-border-hairline)">
              <span style="flex: 1 1 14rem; min-width: 0">
                <span class="ds-checkbox-label">{{ EVENTS_PAGE.label }}</span>
                <span class="ds-checkbox-desc" style="display: block; margin-top: var(--ds-space-1)">{{ EVENTS_PAGE.hint }}</span>
              </span>
              <span style="display: flex; gap: var(--ds-space-7); flex: none">
                <label class="ds-switch">
                  <input type="checkbox" :aria-label="`${EVENTS_PAGE.label} visible`" :checked="isVisible(EVENTS_PAGE.key)" @change="setVisible(EVENTS_PAGE.key, ($event.target as HTMLInputElement).checked)" />
                  <span class="ds-switch-track"><span class="ds-switch-thumb"></span></span>
                  <span class="ds-switch-label">Visible</span>
                </label>
                <label class="ds-switch" :style="{ opacity: isVisible(EVENTS_PAGE.key) ? 1 : 0.45 }">
                  <input type="checkbox" :aria-label="`${EVENTS_PAGE.label} published`" :checked="isPublished(EVENTS_PAGE.key)" :disabled="!isVisible(EVENTS_PAGE.key)" @change="setPublished(EVENTS_PAGE.key, ($event.target as HTMLInputElement).checked)" />
                  <span class="ds-switch-track"><span class="ds-switch-thumb"></span></span>
                  <span class="ds-switch-label">Published</span>
                </label>
              </span>
            </div>
        </div>

        <div class="ds-field" style="gap: var(--ds-space-2); margin-top: var(--ds-space-4)">
          <span class="ds-field-label">Other pages</span>
            <div v-for="page in OTHER_PAGES" :key="page.key" class="page-visibility-row" :data-page="page.key" style="width: 100%; display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-5); flex-wrap: wrap; padding: var(--ds-space-4) 0; border-top: 1px solid var(--ds-border-hairline)">
              <span style="flex: 1 1 14rem; min-width: 0">
                <span class="ds-checkbox-label">{{ page.label }}</span>
              </span>
              <span style="display: flex; gap: var(--ds-space-7); flex: none">
                <label class="ds-switch">
                  <input type="checkbox" :aria-label="`${page.label} visible`" :checked="isVisible(page.key)" @change="setVisible(page.key, ($event.target as HTMLInputElement).checked)" />
                  <span class="ds-switch-track"><span class="ds-switch-thumb"></span></span>
                  <span class="ds-switch-label">Visible</span>
                </label>
                <label class="ds-switch" :style="{ opacity: isVisible(page.key) ? 1 : 0.45 }">
                  <input type="checkbox" :aria-label="`${page.label} published`" :checked="isPublished(page.key)" :disabled="!isVisible(page.key)" @change="setPublished(page.key, ($event.target as HTMLInputElement).checked)" />
                  <span class="ds-switch-track"><span class="ds-switch-thumb"></span></span>
                  <span class="ds-switch-label">Published</span>
                </label>
              </span>
            </div>
          <span v-if="errors.maintenance_allowed_page_paths" class="ds-field-error-text">{{ errors.maintenance_allowed_page_paths }}</span>
          <span v-if="errors.maintenance_hidden_page_paths" class="ds-field-error-text">{{ errors.maintenance_hidden_page_paths }}</span>
        </div>

        </template>

        <BaseButton type="button" style="align-self: flex-start" :disabled="saving" @click="save">
          {{ saving ? 'Saving…' : 'Save' }}
        </BaseButton>
      </div>
    </div>
  </div>
</template>
