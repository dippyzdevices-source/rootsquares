<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import { useAuthStore } from '@/stores/auth'
import AuthSidePanel from './AuthSidePanel.vue'
import { errorText } from './errorText'

// Asks the identity provider to email a reset link (ADR 028, auth item D). The answer is always the same sentence, so the page never reveals
// whether an address has an account.
const { t } = useI18n()
const auth = useAuthStore()
const email = ref('')
const error = ref('')
const busy = ref(false)
const sent = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await auth.providerRequestPasswordReset(email.value.trim())
    sent.value = true
  } catch (e) {
    error.value = errorText(t, e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="si-bg"><section class="si"><div class="si-form"><div class="si-in">
    <span class="rs-eyebrow">{{ t('pages.forgotPassword') }}</span>
    <h1>{{ t('plat.forgot.titleLead') }} <em>{{ t('plat.forgot.titleEm') }}</em></h1>
    <p class="bs-mute" style="margin: 0">{{ t('plat.forgot.lede') }}</p>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
    <AppAlert v-if="sent" tone="success">{{ t('plat.forgot.sent') }}</AppAlert>
    <form v-else style="display: grid; gap: 14px" novalidate @submit.prevent="submit">
      <AppField v-model="email" type="email" :label="t('plat.login.email')" autocomplete="email" />
      <AppButton icon="mail" type="submit" size="lg" block :loading="busy" :disabled="!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())">{{ busy ? t('plat.forgot.busy') : t('plat.forgot.submit') }}</AppButton>
    </form>
    <p class="bs-mute" style="margin: 0; font-size: var(--text-sm)"><RouterLink to="/login">{{ t('plat.forgot.back') }}</RouterLink></p>
  </div></div>
  <AuthSidePanel /></section></div>
</template>
