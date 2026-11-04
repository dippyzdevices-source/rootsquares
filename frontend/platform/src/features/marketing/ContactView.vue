<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { sendContact } from '@/services/marketing'

// Contact, from "Contact Page.html" of the design project (W13-R58): one card, the form on the left (topic pills, name and email, organisation,
// message, send) and "Prefer to skip the form?" on the right (e-mail, support, sign in). Sending disables the button; success replaces the form with
// a confirmation; failure shows an alert with Try again. English only. The addresses are placeholders until the user gives the real ones, and
// sending is still a demo (nothing leaves the browser): see MISSING.md.
const { t } = useI18n()
const { push } = useToast()

const topics = ['start', 'pricing', 'moving', 'other'] as const
const form = reactive({ type: 'start' as string, name: '', email: '', organisation: '', message: '' })
const touched = reactive({ name: false, email: false, message: false })
const sending = ref(false)
const sent = ref(false)
const failed = ref(false)
const sentTo = ref('')

const errors = computed(() => ({
  name: form.name.trim() ? '' : t('marketing.contact.errors.name'),
  email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email) ? '' : t('marketing.contact.errors.email'),
  message: form.message.trim().length >= 10 ? '' : t('marketing.contact.errors.message'),
}))
const show = (k: 'name' | 'email' | 'message') => (touched[k] ? errors.value[k] : '')

async function submit() {
  touched.name = touched.email = touched.message = true
  if (errors.value.name || errors.value.email || errors.value.message) return
  sending.value = true
  failed.value = false
  try {
    await sendContact({ ...form })
    sentTo.value = form.email
    sent.value = true
    push(t('marketing.contact.doneTitle'), 'success')
  } catch {
    failed.value = true
  } finally {
    sending.value = false
  }
}
function reset() {
  Object.assign(form, { type: 'start', name: '', email: '', organisation: '', message: '' })
  touched.name = touched.email = touched.message = false
  sent.value = false
}
</script>

<template>
  <div class="ct-bg">
    <section class="ct">
      <div class="ct-form">
        <span class="rs-eyebrow">{{ t('marketing.contact.eyebrow') }}</span>
        <h1>{{ t('marketing.contact.title') }} <em>{{ t('marketing.contact.titleEm') }}</em></h1>
        <p class="bs-mute" style="margin: 0">{{ t('marketing.contact.lede') }}</p>
        <AppAlert v-if="sent" tone="success" :title="t('marketing.contact.doneTitle')">
          {{ t('marketing.contact.done', { email: sentTo }) }}
          <template #action><AppButton variant="secondary" size="sm" @click="reset">{{ t('marketing.contact.another') }}</AppButton></template>
        </AppAlert>
        <form v-else class="ct-fields" novalidate @submit.prevent="submit">
          <AppAlert v-if="failed" tone="danger" :title="t('marketing.contact.errorTitle')">
            {{ t('marketing.contact.errorText') }}
            <template #action><AppButton variant="secondary" size="sm" @click="failed = false">{{ t('marketing.contact.retry') }}</AppButton></template>
          </AppAlert>
          <fieldset class="ct-topics">
            <legend class="rs-label">{{ t('marketing.contact.topic') }}</legend>
            <label v-for="k in topics" :key="k"><input v-model="form.type" type="radio" name="topic" :value="k"><span>{{ t(`marketing.contact.topics.${k}`) }}</span></label>
          </fieldset>
          <div class="ct-row">
            <AppField v-model="form.name" :label="t('marketing.contact.name')" autocomplete="name" placeholder="Ingrid Haugen" :error="show('name')" @blur="touched.name = true" />
            <AppField v-model="form.email" :label="t('marketing.contact.email')" type="email" autocomplete="email" placeholder="name@example.com" :error="show('email')" @blur="touched.email = true" />
          </div>
          <AppField v-model="form.organisation" :label="t('marketing.contact.organisation')" optional :optional-label="t('marketing.contact.optional')" placeholder="Nordlys Sailing Club" autocomplete="organization" />
          <AppField v-model="form.message" as="textarea" :label="t('marketing.contact.message')" :placeholder="t('marketing.contact.messagePlaceholder')" :error="show('message')" @blur="touched.message = true" />
          <AppButton type="submit" size="lg" block :disabled="sending" :loading="sending" style="min-height: 48px">{{ sending ? t('marketing.contact.sending') : t('marketing.contact.send') }}</AppButton>
          <p class="bs-mute" style="margin: 0; font-size: var(--text-xs)">{{ t('marketing.contact.note') }} <RouterLink to="/privacy">{{ t('marketing.contact.privacy') }}</RouterLink>.</p>
        </form>
      </div>
      <aside class="ct-side">
        <h2>{{ t('marketing.contact.sideTitle') }} <em>{{ t('marketing.contact.sideEm') }}</em></h2>
        <div class="ct-ch">
          <div><small>{{ t('marketing.contact.channels.email') }}</small><a :href="`mailto:${t('marketing.contact.channels.emailValue')}`">{{ t('marketing.contact.channels.emailValue') }}</a><span>{{ t('marketing.contact.channels.emailNote') }}</span></div>
          <div><small>{{ t('marketing.contact.channels.support') }}</small><a :href="`mailto:${t('marketing.contact.channels.supportValue')}`">{{ t('marketing.contact.channels.supportValue') }}</a><span>{{ t('marketing.contact.channels.supportNote') }}</span></div>
        </div>
        <p class="ct-alt">{{ t('marketing.contact.haveSquare') }} <RouterLink to="/login">{{ t('marketing.contact.signIn') }}</RouterLink> {{ t('marketing.contact.fasterSupport') }}</p>
      </aside>
    </section>
  </div>
</template>
