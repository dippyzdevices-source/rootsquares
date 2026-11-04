<script setup lang="ts">
import PageHeading from '../../layout-themes/parts/PageHeading.vue'
import { activeLayout } from '../../layout-themes/layouts'
const themed = activeLayout !== null // a layout theme sets the page heading and lists (W9-R5)
import { moduleEnabled, offeredPhrase } from '../../services/modules'
import { usePageHeading } from '../../composables/usePageHeading'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import { fetchSettings } from '../../services/settingsApi'
import { useLookup } from '../../composables/useLookup'
import { EMPTY_CONTACT_PAGE, loadHomeContent, type ContactPage } from '../../services/siteContent'
import { submitContactForm, ValidationError } from '../../services/contactApi'
import { mapEmbedUrl, mapOpenUrl, mapDirectionsUrl } from '../../utils/mapLinks'

const email = ref('')
const phone = ref('')
const address = ref('')
const showMap = ref(false)

// The extra parts of the page are the square's own words (W7-R9): no questions = no section, no footnote text = no line.
const extra = ref<ContactPage>({ ...EMPTY_CONTACT_PAGE })
onMounted(async () => {
  extra.value = (await loadHomeContent()).contact_page
  try {
    const settings = await fetchSettings()
    email.value = settings.contact_email
    phone.value = settings.contact_phone
    address.value = settings.contact_address
  } catch {
    // Contact details are secondary to the page's static copy — fail quietly rather than
    // block rendering the rest of the page.
  }
})

// What a message can be about is a list the square's admin edits (Settings, Lists, Contact reasons); the label is sent as the email subject.
const { options: reasonOptions } = useLookup('contact_reason')
const reasons = computed(() => (reasonOptions.value.length ? reasonOptions.value : [{ value: 'general', label: 'General enquiry' }]))
// `/contact?reason=photos` (the gallery's "Contribute photographs" button) preselects that reason and prefills a starter message when the
// square's list has it; an unknown value falls back to the first reason.
const route = useRoute()
const PHOTOS_STARTER = 'I have photographs from (year / event): '
const form = ref({
  name: '',
  email: '',
  reason: '',
  message: '',
  website: '',
})
let started = false
watch(
  reasons,
  (list) => {
    if (!list.some((r) => r.value === form.value.reason)) form.value.reason = list[0]!.value
    if (!started) {
      started = true
      const wanted = String(route.query.reason ?? '')
      if (list.some((r) => r.value === wanted)) {
        form.value.reason = wanted
        if (wanted === 'photos') form.value.message = PHOTOS_STARTER
      }
    }
  },
  { immediate: true },
)
const consent = ref(false)
const sent = ref(false)
const sending = ref(false)
const formError = ref('')
const fieldErrors = ref<Record<string, string>>({})
const MESSAGE_MAX = 1200

// Submits to the backend Contact Us API (POST /api/contact), which sends the message on to
// the association's contact address via Resend — see backend/app/contact/routes.py. `website`
// is a hidden honeypot field real visitors never fill in.
async function submit() {
  formError.value = ''
  fieldErrors.value = {}
  if (!form.value.name.trim() || !form.value.email.includes('@')) {
    formError.value = 'We need a name and an email address we can reply to.'
    return
  }
  if (!consent.value) {
    formError.value = 'Please confirm we may use your message to reply to you.'
    return
  }

  const reasonLabel = reasons.value.find((r) => r.value === form.value.reason)?.label ?? form.value.reason

  sending.value = true
  try {
    await submitContactForm({
      name: form.value.name.trim(),
      email: form.value.email.trim(),
      subject: reasonLabel,
      message: form.value.message.trim(),
      website: form.value.website,
    })
    sent.value = true
  } catch (err) {
    if (err instanceof ValidationError) {
      fieldErrors.value = err.errors
      formError.value = 'Please check the highlighted fields below.'
    } else {
      formError.value = err instanceof Error ? err.message : "We couldn't send your message right now. Please try again later."
    }
  } finally {
    sending.value = false
  }
}

function writeAnother() {
  sent.value = false
  formError.value = ''
  fieldErrors.value = {}
  form.value = { name: '', email: '', reason: reasons.value[0]!.value, message: '', website: '' }
  consent.value = false
}

const messageLength = computed(() => form.value.message.length)

const faqs = computed(() => extra.value.faq)
const openFaq = ref<number | null>(0)
function toggleFaq(i: number) {
  openFaq.value = openFaq.value === i ? null : i
}
const heading = usePageHeading('contact', () => ({ eyebrow: 'Get in touch', title: 'Contact us', intro: offeredPhrase() ? `Questions about ${offeredPhrase()}? Send us a message below, or reach us directly.` : 'Send us a message below, or reach us directly.' }))
</script>

<template>
  <div class="ds-scope">
    <PageHeading v-if="themed" :heading="heading" />
    <section v-else class="ds-band ds-band-wash" style="padding-bottom: var(--ds-space-6)">
      <div class="ds-container ds-heading">
        <span v-if="heading.script_line" class="ds-script">{{ heading.script_line }}</span>
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />{{ heading.eyebrow }}</span>
        <h1 class="ds-display ds-display-m">{{ heading.title }}</h1>
        <p v-if="heading.local_line" class="ds-bn" style="font-size: var(--ds-text-subtitle); color: var(--ds-text-muted)">{{ heading.local_line }}</p>
        <p class="ds-intro">{{ heading.intro }}</p>
      </div>
    </section>

    <section class="ds-band ds-band-paper" style="padding-top: var(--ds-space-6)">
      <div class="ds-container ds-row ds-row--sidebar">
        <div>
          <div v-if="sent" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
            <div class="ds-alert ds-alert-success">
              <div style="flex: 1">
                <strong class="ds-alert-title">Message sent</strong>
                Your message has been sent successfully. We'll get back to you soon.
              </div>
              <BaseButton type="button" variant="ghost" size="sm" style="flex-shrink: 0" @click="writeAnother">Write another</BaseButton>
            </div>
          </div>

          <div v-else class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-5)">
            <div>
              <h2 class="ds-title">Send us a message</h2>
              <p class="ds-meta" style="margin-top: var(--ds-space-1)">Everything below is required. We never pass your details on.</p>
            </div>

            <div v-if="formError" class="ds-alert ds-alert-danger">
              <div>
                <strong class="ds-alert-title">Not quite ready to send</strong>
                {{ formError }}
              </div>
            </div>

            <div class="ds-cards ds-cards--2" style="display: grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr); gap: var(--ds-space-4)">
              <label class="ds-field">
                <span class="ds-field-label">Your name</span>
                <span class="ds-field-control"><input v-model="form.name" type="text" placeholder="Your full name" class="ds-field-input" /></span>
                <span v-if="fieldErrors.name" class="ds-field-error-text">{{ fieldErrors.name }}</span>
              </label>
              <label class="ds-field">
                <span class="ds-field-label">Email</span>
                <span class="ds-field-control"><input v-model="form.email" type="email" placeholder="you@example.com" class="ds-field-input" /></span>
                <span v-if="fieldErrors.email" class="ds-field-error-text">{{ fieldErrors.email }}</span>
                <span v-else class="ds-field-hint">We reply here.</span>
              </label>
            </div>
            <label style="position: absolute; left: -9999px; opacity: 0" aria-hidden="true" tabindex="-1">
              Leave this field empty
              <input v-model="form.website" type="text" name="website" autocomplete="off" tabindex="-1" />
            </label>

            <label class="ds-field">
              <span class="ds-field-label">What is it about?</span>
              <BaseSelect v-model="form.reason" :options="reasons" />
            </label>

            <label class="ds-field">
              <span class="ds-field-label">Message</span>
              <span class="ds-textarea-control">
                <textarea v-model="form.message" rows="6" :maxlength="MESSAGE_MAX" placeholder="Tell us what you need. If it's about an event, mention which one and the date." class="ds-textarea"></textarea>
              </span>
              <span class="ds-textarea-count">{{ messageLength }} / {{ MESSAGE_MAX }}</span>
              <span v-if="fieldErrors.message" class="ds-field-error-text">{{ fieldErrors.message }}</span>
            </label>

            <label class="ds-checkbox">
              <input v-model="consent" type="checkbox" />
              <span class="ds-checkbox-box">✓</span>
              <span>
                <span class="ds-checkbox-label">You may use this message to reply to you</span>
                <span class="ds-checkbox-desc">We only use it to answer your enquiry.</span>
              </span>
            </label>

            <div style="display: flex; gap: var(--ds-space-3); flex-wrap: wrap; align-items: center">
              <BaseButton type="button" size="lg" :disabled="sending" @click="submit">
                {{ sending ? 'Sending…' : 'Send message' }}
                <svg v-if="!sending" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></svg>
              </BaseButton>
              <span v-if="email" class="ds-caption">Or write straight to <a :href="`mailto:${email}`" style="color: var(--ds-text-primary)">{{ email }}</a></span>
            </div>
          </div>
        </div>

        <div style="display: flex; flex-direction: column; gap: var(--ds-space-5)">
          <div class="ds-card ds-card-outline" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
            <div v-if="address" style="display: grid; grid-template-columns: 18px minmax(0,1fr); gap: var(--ds-space-3)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--ds-text-primary); margin-top: 3px"><path d="M21 10c0 6-9 12-9 12s-9-6-9-12a9 9 0 0 1 18 0Z" /><circle cx="12" cy="10" r="3" /></svg>
              <div>
                <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow)">Address</p>
                <p class="ds-body" style="margin-top: 2px">{{ address }}</p>
              </div>
            </div>
            <div v-if="phone" style="display: grid; grid-template-columns: 18px minmax(0,1fr); gap: var(--ds-space-3)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--ds-text-primary); margin-top: 3px"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" /></svg>
              <div>
                <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow)">Phone</p>
                <p class="ds-body" style="margin-top: 2px"><a :href="`tel:${phone.replace(/\s+/g, '')}`" style="color: inherit">{{ phone }}</a></p>
              </div>
            </div>
            <div v-if="email" style="display: grid; grid-template-columns: 18px minmax(0,1fr); gap: var(--ds-space-3)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--ds-text-primary); margin-top: 3px"><rect x="2" y="4" width="20" height="16" rx="2" /><path d="m22 6-10 7L2 6" /></svg>
              <div>
                <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow)">Email</p>
                <p class="ds-body" style="margin-top: 2px"><a :href="`mailto:${email}`" style="color: inherit">{{ email }}</a></p>
              </div>
            </div>
          </div>

          <div class="contact-map">
            <iframe
              v-if="showMap && address"
              class="contact-map-frame"
              :src="mapEmbedUrl(address)"
              :title="`Map of ${address}`"
              loading="lazy"
              referrerpolicy="no-referrer-when-downgrade"
              allowfullscreen
            />
            <div v-else class="contact-map-placeholder">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--ds-text-faint); margin: 0 auto"><path d="M3 6v15l6-3 6 3 6-3V3l-6 3-6-3-6 3Z" /><path d="M9 3v15" /><path d="M15 6v15" /></svg>
              <p class="ds-eyebrow" style="margin-top: var(--ds-space-2); font-size: var(--ds-text-eyebrow)">Map</p>
              <p v-if="address" class="ds-caption" style="margin-top: 4px">{{ address }}</p>
              <BaseButton v-if="address" type="button" size="sm" class="show-map" style="margin-top: var(--ds-space-3)" @click="showMap = true">
                Show map
              </BaseButton>
              <p v-if="address" class="ds-caption" style="margin-top: var(--ds-space-2)">The map loads from Google Maps only when you ask for it.</p>
            </div>
          </div>
          <div v-if="address" class="contact-map-links">
            <BaseButton :href="mapOpenUrl(address)" size="sm" variant="secondary" class="open-map" target="_blank" rel="noopener noreferrer">Open in Maps</BaseButton>
            <BaseButton :href="mapDirectionsUrl(address)" size="sm" variant="secondary" class="map-directions" target="_blank" rel="noopener noreferrer">Get directions</BaseButton>
          </div>
        </div>
      </div>
    </section>

    <section v-if="faqs.length" class="ds-band ds-band-card" style="border-top: 1px solid var(--ds-border-hairline)">
      <div class="ds-container" style="max-width: var(--ds-container-narrow); margin: 0 auto">
        <div v-if="extra.faq_eyebrow || extra.faq_title" class="ds-heading ds-heading--center">
          <span v-if="extra.faq_eyebrow" class="ds-eyebrow"><span class="ds-eyebrow-rule" />{{ extra.faq_eyebrow }}</span>
          <h2 v-if="extra.faq_title" class="ds-display ds-display-s">{{ extra.faq_title }}</h2>
        </div>
        <div class="ds-motif" style="margin: var(--ds-space-6) auto">
          <span></span><span class="ds-motif-glyph">❖</span><span></span>
        </div>
        <div class="ds-accordion">
          <div v-for="(faq, i) in faqs" :key="faq.title" class="ds-accordion-item">
            <h3 style="margin: 0">
              <button type="button" class="ds-accordion-trigger" :class="{ 'ds-accordion-trigger-open': openFaq === i }" :aria-expanded="openFaq === i" @click="toggleFaq(i)">
                <span>{{ faq.title }}</span>
                <span class="ds-accordion-icon" :class="{ 'ds-accordion-icon-open': openFaq === i }" aria-hidden="true">+</span>
              </button>
            </h3>
            <div class="ds-accordion-panel" :class="{ 'ds-accordion-panel-open': openFaq === i }">
              <div class="ds-accordion-panel-inner">
                <p class="ds-accordion-content">{{ faq.content }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <p v-if="extra.footnote_text || extra.footnote_link" style="text-align: center; padding: var(--ds-space-6) 0" class="ds-meta">
      {{ extra.footnote_text }}
      <router-link v-if="extra.footnote_link && moduleEnabled('memberships')" to="/membership" style="color: var(--ds-text-primary); font-weight: 600">{{ extra.footnote_link }}</router-link>
    </p>
  </div>
</template>

<style scoped>
.contact-map {
  position: relative;
  border-radius: var(--ds-radius-md);
  overflow: hidden;
  border: 1px solid var(--ds-border-hairline);
  aspect-ratio: 4 / 3;
  background: var(--ds-surface-sunken);
  background-image: var(--ds-grain);
  display: flex;
  align-items: center;
  justify-content: center;
}
.contact-map-frame { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; }
.contact-map-placeholder { text-align: center; padding: var(--ds-space-4); }
.contact-map-links { display: flex; flex-wrap: wrap; justify-content: center; gap: var(--ds-space-2); }
</style>
