<script setup lang="ts">
import { computed, onMounted, ref, useId } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import { useAuthStore } from '@/stores/auth'
import AuthSidePanel from './AuthSidePanel.vue'
import { errorText } from './errorText'

// Where the emailed reset link lands (ADR 028, auth item D). The provider turns the link into a short recovery session (Supabase) or hands over
// a token in the address (Neon); the form only appears when one of them is there.
const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const checking = ref(true)
const linkOk = ref(false)
const password = ref('')
const again = ref('')
const error = ref('')
const busy = ref(false)
const showPw = ref(false)
const pwId = useId()
const againId = useId()
const valid = computed(() => password.value.length >= 10 && password.value === again.value)

onMounted(async () => {
  try { linkOk.value = await auth.providerHasRecoverySession() } catch { linkOk.value = false }
  checking.value = false
})

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await auth.providerUpdatePassword(password.value)
    await router.push('/dashboard')
  } catch (e) {
    error.value = errorText(t, e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="si-bg"><section class="si"><div class="si-form"><div class="si-in">
    <span class="rs-eyebrow">{{ t('pages.resetPassword') }}</span>
    <h1>{{ t('plat.reset.titleLead') }} <em>{{ t('plat.reset.titleEm') }}</em></h1>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
    <p v-if="checking" class="bs-mute" style="margin: 0">{{ t('plat.reset.checking') }}</p>
    <form v-else-if="linkOk" style="display: grid; gap: 14px" novalidate @submit.prevent="submit">
      <div class="rs-field">
        <label class="rs-label" :for="pwId">{{ t('plat.reset.password') }}</label>
        <div class="si-pw">
          <input :id="pwId" v-model="password" class="rs-input" :type="showPw ? 'text' : 'password'" autocomplete="new-password" aria-describedby="reset-pw-hint">
          <button type="button" :aria-label="showPw ? t('plat.login.hidePassword') : t('plat.login.showPassword')" :aria-pressed="showPw" @click="showPw = !showPw">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /><path v-if="showPw" d="M4 20 20 4" /></svg>
          </button>
        </div>
        <p id="reset-pw-hint" class="bs-mute" style="margin: 4px 0 0; font-size: var(--text-xs)">{{ t('plat.signup.passwordHint') }}</p>
      </div>
      <div class="rs-field">
        <label class="rs-label" :for="againId">{{ t('plat.reset.again') }}</label>
        <div class="si-pw">
          <input :id="againId" v-model="again" class="rs-input" :type="showPw ? 'text' : 'password'" autocomplete="new-password" :aria-invalid="again && password !== again ? true : undefined">
          <button type="button" :aria-label="showPw ? t('plat.login.hidePassword') : t('plat.login.showPassword')" :aria-pressed="showPw" @click="showPw = !showPw">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /><path v-if="showPw" d="M4 20 20 4" /></svg>
          </button>
        </div>
        <p v-if="again && password !== again" role="alert" style="margin: 4px 0 0; font-size: var(--text-xs); color: var(--color-danger)">{{ t('plat.reset.mismatch') }}</p>
      </div>
      <AppButton icon="key" type="submit" size="lg" block :loading="busy" :disabled="!valid">{{ busy ? t('plat.reset.busy') : t('plat.reset.submit') }}</AppButton>
    </form>
    <AppAlert v-else tone="danger" :title="t('plat.reset.badTitle')">{{ t('plat.reset.badText') }}</AppAlert>
    <p class="bs-mute" style="margin: 0; font-size: var(--text-sm)"><RouterLink :to="linkOk ? '/dashboard' : '/forgot-password'">{{ linkOk ? t('plat.reset.skip') : t('plat.reset.askAgain') }}</RouterLink></p>
  </div></div>
  <AuthSidePanel /></section></div>
</template>
