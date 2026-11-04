<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppCheck from '@rootsquares/ui/components/AppCheck.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import { errorText } from '@/features/platform/errorText'
import { platform } from '@/services/platform'

// Pricing page, "Nothing fits you? Speak to us" (W19-R22): a visitor leaves a name, an e-mail and a phone number (and, if they like, what they need);
// it goes to the prospect list of the owner console. Nothing is sent by e-mail and nothing is created for the visitor. `website` is a hidden field only a bot fills.
const { t } = useI18n()
const form = ref({ name: '', email: '', phone: '', message: '' })
const consent = ref(false)
const website = ref('')
const busy = ref(false)
const done = ref(false)
const error = ref('')
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const phoneOk = computed(() => (form.value.phone.match(/\d/g) ?? []).length >= 6)
const valid = computed(() => form.value.name.trim().length >= 2 && EMAIL.test(form.value.email.trim()) && phoneOk.value && consent.value)

async function send() {
  if (!valid.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    await platform.submitProspect({ name: form.value.name.trim(), email: form.value.email.trim(), phone: form.value.phone.trim(), message: form.value.message.trim() || undefined, consent: true, website: website.value })
    done.value = true
  } catch (e) { error.value = errorText(t, e) } finally { busy.value = false }
}
</script>

<template>
  <section class="cr" data-testid="pricing-custom" aria-labelledby="cr-h">
    <div class="cr-text">
      <span class="rs-eyebrow">{{ t('marketing.pricing.custom.eyebrow') }}</span>
      <h2 id="cr-h">{{ t('marketing.pricing.custom.title') }}</h2>
      <p class="bs-mute">{{ t('marketing.pricing.custom.text') }}</p>
      <ul class="cr-pts"><li>{{ t('marketing.pricing.custom.p1') }}</li><li>{{ t('marketing.pricing.custom.p2') }}</li><li>{{ t('marketing.pricing.custom.p3') }}</li></ul>
    </div>
    <div class="cr-form">
      <AppAlert v-if="done" tone="success" :title="t('marketing.pricing.custom.doneTitle')">{{ t('marketing.pricing.custom.doneBody') }}</AppAlert>
      <form v-else novalidate @submit.prevent="send">
        <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
        <AppField v-model="form.name" :label="t('marketing.pricing.custom.name')" autocomplete="name" />
        <AppField v-model="form.email" type="email" :label="t('marketing.pricing.custom.email')" autocomplete="email" />
        <AppField v-model="form.phone" type="tel" :label="t('marketing.pricing.custom.phone')" autocomplete="tel" />
        <AppField v-model="form.message" as="textarea" :rows="3" :max="1000" :label="t('marketing.pricing.custom.message')" optional :optional-label="t('common.optional')" />
        <input v-model="website" class="cr-hp" type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
        <AppCheck v-model="consent" :label="t('marketing.pricing.custom.consent')" />
        <AppButton type="submit" size="lg" block :loading="busy" :disabled="!valid" style="min-height: 48px">{{ t('marketing.pricing.custom.cta') }}</AppButton>
      </form>
    </div>
  </section>
</template>

<style scoped>
.cr { margin: 32px var(--page-x) 8px; padding: 40px 44px; display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 36px 56px; align-items: start; border: 1px solid var(--color-border-strong); border-radius: var(--shape-surface); background: var(--color-surface); box-shadow: inset 0 3px 0 var(--color-brass); }
.cr-text { display: grid; gap: 14px; align-content: start; }
.cr-text h2 { margin: 0; font: 500 clamp(34px, 4.4vw, 52px)/1.05 var(--font-display); letter-spacing: -0.015em; }
.cr-text p { margin: 0; font-size: var(--text-lg); max-width: 46ch; }
.cr-pts { margin: 6px 0 0; padding-inline-start: 20px; display: grid; gap: 8px; font-size: var(--text-base); color: var(--color-text-muted); }
.cr-form form { display: grid; gap: 14px; }
.cr-hp { position: absolute; left: -9999px; width: 1px; height: 1px; opacity: 0; }
@media (max-width: 860px) { .cr { grid-template-columns: 1fr; padding: 26px 20px; } }
</style>
