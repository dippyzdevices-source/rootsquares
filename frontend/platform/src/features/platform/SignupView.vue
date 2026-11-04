<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { startQuery } from './startFlow'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import { providerEnabled } from '@/services/authProvider'
import { USE_MOCK } from '@/services/platform'
import { useAuthStore } from '@/stores/auth'
import GoogleButton from './GoogleButton.vue'
import { errorText } from './errorText'

// Without a provider: POST /auth/signup creates the user and the organisation and signs in with an httpOnly cookie. With one (ADR 028):
// the provider creates the account (it may ask to verify the email first), then POST /organizations creates the organisation.
const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const form = ref({ name: '', organization_name: '', email: '', password: '' })
const error = ref('')
const busy = ref(false)
const verify = ref(false)
const showPw = ref(false)
const pwId = useId()
const valid = computed(() => form.value.organization_name.trim().length >= 2 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.value.email) && form.value.password.length >= 10)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    const input = { ...form.value, email: form.value.email.trim() }
    if (providerEnabled) {
      if ((await auth.providerSignup(input)) === 'verify') { verify.value = true; return }
    } else {
      await auth.signup(input)
    }
    await router.push({ path: '/squares/new', query: startQuery(route.query) })
  } catch (e) {
    error.value = errorText(t, e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="si-bg"><section class="si"><div class="si-form"><div class="si-in">
    <span class="rs-eyebrow">{{ t('pages.signup') }}</span>
    <h1>{{ t('plat.signup.titleLead') }} <em>{{ t('plat.signup.titleEm') }}</em></h1>
    <p class="bs-mute" style="margin: 0">{{ t('plat.signup.lede') }}</p>
    <AppAlert v-if="USE_MOCK" tone="info">{{ t('plat.mockBanner') }}</AppAlert>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
    <AppAlert v-if="verify" tone="info">{{ t('plat.signup.verify') }}</AppAlert>
    <template v-if="providerEnabled && !verify">
      <GoogleButton :label="t('plat.google.signup')" @error="error = $event" />
      <div class="si-or"><span>{{ t('plat.login.orEmail') }}</span></div>
    </template>
    <form v-if="!verify" style="display: grid; gap: 14px" novalidate @submit.prevent="submit">
      <AppField v-model="form.name" :label="t('plat.signup.name')" autocomplete="name" optional :optional-label="t('common.optional')" />
      <AppField v-model="form.organization_name" :label="t('plat.signup.org')" autocomplete="organization" />
      <AppField v-model="form.email" type="email" :label="t('plat.signup.email')" autocomplete="email" />
      <div class="rs-field">
        <label class="rs-label" :for="pwId">{{ t('plat.signup.password') }}</label>
        <div class="si-pw">
          <input :id="pwId" v-model="form.password" class="rs-input" :type="showPw ? 'text' : 'password'" autocomplete="new-password" aria-describedby="signup-pw-hint">
          <button type="button" :aria-label="showPw ? t('plat.login.hidePassword') : t('plat.login.showPassword')" :aria-pressed="showPw" @click="showPw = !showPw">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /><path v-if="showPw" d="M4 20 20 4" /></svg>
          </button>
        </div>
        <p id="signup-pw-hint" class="bs-mute" style="margin: 4px 0 0; font-size: var(--text-xs)">{{ t('plat.signup.passwordHint') }}</p>
      </div>
      <AppButton icon="plus" type="submit" size="lg" block :loading="busy" :disabled="!valid">{{ busy ? t('plat.signup.busy') : t('plat.signup.submit') }}</AppButton>
    </form>
    <p class="bs-mute" style="margin: 0; font-size: var(--text-sm)">{{ t('plat.signup.haveAccount') }} <RouterLink :to="{ path: '/login', query: startQuery(route.query) }">{{ t('plat.signup.signinLink') }}</RouterLink></p>
  </div></div>
  <aside class="si-side" aria-hidden="true">
    <div class="si-brand">
      <svg class="si-art" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" stroke-width="2.2" /><path d="M12 4v9M12 9l-4 3M12 9l4 3" stroke="var(--color-brass)" stroke-width="2.2" stroke-linecap="round" /></svg>
      <span class="si-name">rootsquares</span>
      <span class="si-sub">{{ t('plat.login.brandSub') }} <em>{{ t('plat.login.brandSubEm') }}</em></span>
    </div>
    <p class="si-q">{{ t('plat.login.sideLead') }} <em>{{ t('plat.login.sideEm') }}</em></p>
  </aside></section></div>
</template>
