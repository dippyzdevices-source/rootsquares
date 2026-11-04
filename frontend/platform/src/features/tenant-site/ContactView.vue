<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@rootsquares/ui/components/useToast'
import { joinMembership } from '@/services/api'
import { ORG } from '@/mock/bca'
import TButton from './components/TButton.vue'
import TField from './components/TField.vue'

const { t } = useI18n()
const { push } = useToast()
const form = reactive({ name: '', email: '', message: '' })
const touched = ref(false)
const busy = ref(false)
const sent = ref(false)
const errors = computed(() => ({
  name: form.name.trim() ? '' : t('site.joinNameError'),
  email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email) ? '' : t('site.joinEmailError'),
  message: form.message.trim().length >= 10 ? '' : t('site.contactMessageError'),
}))
async function submit() {
  touched.value = true
  if (errors.value.name || errors.value.email || errors.value.message) return
  busy.value = true
  await joinMembership()
  busy.value = false
  sent.value = true
  push(t('site.contactSent'), 'success', t('site.contactSentBody'))
}
</script>

<template>
  <section class="t-sec">
    <div class="t-wrap">
      <h1 style="font-size: clamp(32px, 5vw, 48px)">{{ t('site.contactTitle') }}</h1>
      <p class="t-muted" style="margin: 8px 0 24px">{{ t('site.contactText') }}</p>
      <div class="t-detail">
        <div class="t-card">
          <div v-if="sent" class="t-stack"><h2 style="font-size: 26px">{{ t('site.contactSent') }}</h2><p>{{ t('site.contactSentBody') }}</p></div>
          <form v-else class="t-stack" novalidate @submit.prevent="submit">
            <TField v-model="form.name" :label="t('site.contactName')" autocomplete="name" :error="touched ? errors.name : ''" />
            <TField v-model="form.email" type="email" :label="t('site.contactEmail')" autocomplete="email" :error="touched ? errors.email : ''" />
            <TField v-model="form.message" as="textarea" :label="t('site.contactMessage')" :error="touched ? errors.message : ''" />
            <div><TButton type="submit" :disabled="busy">{{ t('site.contactSend') }}</TButton></div>
          </form>
        </div>
        <div class="t-card t-card--sunken">
          <h2 style="font-size: 22px; margin-bottom: 8px">{{ t('site.address') }}</h2>
          <p style="margin: 0">{{ ORG.fullName }}<br>{{ ORG.place }}<br><a :href="`mailto:${ORG.email}`">{{ ORG.email }}</a></p>
        </div>
      </div>
    </div>
  </section>
</template>
