<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import { errorText } from '@/errorText'
import { useStaffStore } from '@/stores/staff'

// Step two of the staff sign-in: the code of the authenticator app, or a recovery code.
const { t } = useI18n()
const router = useRouter()
const staff = useStaffStore()
const code = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await staff.totp(code.value.trim())
    await router.push('/')
  } catch (e) {
    error.value = errorText(t, e)
  } finally {
    busy.value = false
  }
}
async function startAgain() {
  await staff.logout()
  await router.push('/sign-in')
}
</script>

<template>
  <div class="si-bg"><section class="si"><div class="si-form"><div class="si-in">
    <span class="rs-eyebrow">{{ t('adm.second.eyebrow') }}</span>
    <h1>{{ t('adm.second.titleLead') }} <em>{{ t('adm.second.titleEm') }}</em></h1>
    <p class="bs-mute" style="margin: 0">{{ t('adm.second.lede') }}</p>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
    <form style="display: grid; gap: 14px" novalidate @submit.prevent="submit">
      <AppField v-model="code" :label="t('adm.second.code')" autocomplete="one-time-code" />
      <AppButton icon="shield" type="submit" size="lg" block :loading="busy" :disabled="!code">{{ busy ? t('adm.second.busy') : t('adm.second.submit') }}</AppButton>
    </form>
    <div class="si-ft oc-back"><AppButton variant="secondary" size="sm" icon="chevron-left" @click="startAgain">{{ t('adm.second.back') }}</AppButton></div>
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
