<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import { errorText } from '@/errorText'
import { useStaffStore } from '@/stores/staff'

// Step one of the staff sign-in: e-mail and password. The server answers which step comes next (the second step, or the first set-up of the authenticator app).
const { t } = useI18n()
const router = useRouter()
const staff = useStaffStore()
const email = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await staff.login(email.value.trim(), password.value)
    await router.push(staff.step === 'totp' ? '/second-step' : staff.step === 'enrol' ? '/set-up' : '/')
  } catch (e) {
    error.value = errorText(t, e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="si-bg"><section class="si"><div class="si-form"><div class="si-in">
    <span class="rs-eyebrow">{{ t('adm.signIn.eyebrow') }}</span>
    <h1>{{ t('adm.signIn.titleLead') }} <em>{{ t('adm.signIn.titleEm') }}</em></h1>
    <p class="bs-mute" style="margin: 0">{{ t('adm.signIn.lede') }}</p>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
    <form style="display: grid; gap: 14px" novalidate @submit.prevent="submit">
      <AppField v-model="email" type="email" :label="t('adm.signIn.email')" autocomplete="username" />
      <AppField v-model="password" type="password" :label="t('adm.signIn.password')" autocomplete="current-password" />
      <AppButton icon="key" type="submit" size="lg" block :loading="busy" :disabled="!email || !password">{{ busy ? t('adm.signIn.busy') : t('adm.signIn.submit') }}</AppButton>
    </form>
  </div></div>
  <aside class="si-side" aria-hidden="true">
    <div class="si-brand">
      <svg class="si-art" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" stroke-width="2.2" /><path d="M12 4v9M12 9l-4 3M12 9l4 3" stroke="var(--color-brass)" stroke-width="2.2" stroke-linecap="round" /></svg>
      <span class="si-name">{{ t('adm.name') }}</span>
      <span class="si-sub">{{ t('adm.signIn.brandSub') }} <em>{{ t('adm.signIn.brandSubEm') }}</em></span>
    </div>
    <p class="si-q">{{ t('adm.signIn.sideLead') }} <em>{{ t('adm.signIn.sideEm') }}</em></p>
  </aside></section></div>
</template>
