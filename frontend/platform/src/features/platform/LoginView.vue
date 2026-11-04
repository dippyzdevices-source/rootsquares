<script setup lang="ts">
import { ref, useId } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { startQuery } from './startFlow'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { providerEnabled } from '@/services/authProvider'
import { USE_MOCK } from '@/services/platform'
import { useAuthStore } from '@/stores/auth'
import GoogleButton from './GoogleButton.vue'
import { errorText } from './errorText'

// With an identity provider configured (ADR 028) people sign in through it; without one the platform's own login is used (POST /auth/login, httpOnly cookie).
// Password reset is a stub there: nothing is sent. Staff do not sign in here (ADR 083).
const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const { push } = useToast()
const email = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)
const ownLogin = !providerEnabled // true = the platform's own login (no identity provider)
const showPw = ref(false)
const pwId = useId()
const emailId = useId()

async function submit() {
  error.value = ''
  busy.value = true
  try {
    if (ownLogin) await auth.login(email.value.trim(), password.value)
    else await auth.providerLogin(email.value.trim(), password.value)
    const chosen = startQuery(route.query)
    await router.push(auth.needsOrg ? '/organization/new' : Object.keys(chosen).length ? { path: '/squares/new', query: chosen } : auth.landingPath)
  } catch (e) {
    error.value = errorText(t, e)
  } finally {
    busy.value = false
  }
}
function forgot() {
  if (providerEnabled) void router.push('/forgot-password')
  else push(t('plat.login.resetSent'), 'info') // the platform's own login has no reset yet
}
</script>

<template>
  <div class="si-bg"><section class="si"><div class="si-form"><div class="si-in">
    <span class="rs-eyebrow">{{ t('pages.login') }}</span>
    <h1>{{ t('plat.login.titleLead') }} <em>{{ t('plat.login.titleEm') }}</em></h1>
    <p class="bs-mute" style="margin: 0">{{ t('plat.login.lede') }}</p>
    <AppAlert v-if="USE_MOCK" tone="info">{{ t('plat.mockBanner') }}</AppAlert>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
    <template v-if="providerEnabled">
      <GoogleButton :label="t('plat.google.login')" @error="error = $event" />
      <div class="si-or"><span>{{ t('plat.login.orEmail') }}</span></div>
    </template>
    <form style="display: grid; gap: 14px" novalidate @submit.prevent="submit">
      <div class="rs-field">
        <label class="rs-label" :for="emailId">{{ t('plat.login.email') }}</label>
        <input :id="emailId" v-model="email" class="rs-input" type="email" autocomplete="email" placeholder="name@example.com" :aria-invalid="error ? true : undefined">
      </div>
      <div class="rs-field">
        <div class="bs-row" style="justify-content: space-between">
          <label class="rs-label" :for="pwId">{{ t('plat.login.password') }}</label>
          <a href="#" style="font-size: var(--text-xs)" @click.prevent="forgot">{{ t('plat.login.forgot') }}</a>
        </div>
        <div class="si-pw">
          <input :id="pwId" v-model="password" class="rs-input" :type="showPw ? 'text' : 'password'" autocomplete="current-password" :aria-invalid="error ? true : undefined">
          <button type="button" :aria-label="showPw ? t('plat.login.hidePassword') : t('plat.login.showPassword')" :aria-pressed="showPw" @click="showPw = !showPw">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /><path v-if="showPw" d="M4 20 20 4" /></svg>
          </button>
        </div>
      </div>
      <AppButton icon="key" type="submit" size="lg" block :loading="busy" :disabled="!email || !password">{{ busy ? t('plat.login.busy') : t('plat.login.submit') }}</AppButton>
    </form>
    <p class="bs-mute" style="margin: 0; font-size: var(--text-sm)">{{ t('plat.login.newHere') }} <RouterLink :to="{ path: '/signup', query: startQuery(route.query) }">{{ t('plat.login.createSquare') }}</RouterLink></p>
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
