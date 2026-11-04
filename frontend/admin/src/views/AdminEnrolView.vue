<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import { staffApi, type StaffSessionInfo } from '@/adminApi'
import { errorText } from '@/errorText'
import { qrSvg } from '@/qr'
import { useStaffStore } from '@/stores/staff'

// First sign-in: the person sets up the authenticator app: scan the QR code, or type the key (also a link the phone's app opens).
// After the first correct code the recovery codes are shown once; the sign-in counts only when the person says they have stored them.
const { t } = useI18n()
const router = useRouter()
const staff = useStaffStore()
const secret = ref('')
const uri = ref('')
const code = ref('')
const error = ref('')
const busy = ref(false)
const recovery = ref<string[] | null>(null)
let done: StaffSessionInfo | null = null
const grouped = computed(() => secret.value.replace(/(.{4})/g, '$1 ').trim())
const qr = computed(() => (uri.value ? qrSvg(uri.value) : ''))

onMounted(async () => {
  try {
    const r = await staffApi.enrolStart()
    secret.value = r.secret
    uri.value = r.otpauth_uri
  } catch (e) { error.value = errorText(t, e) }
})
async function confirm() {
  error.value = ''
  busy.value = true
  try {
    const r = await staffApi.enrolConfirm(code.value.trim())
    done = { step: r.step, staff: r.staff }
    recovery.value = r.recovery_codes
  } catch (e) {
    error.value = errorText(t, e)
  } finally {
    busy.value = false
  }
}
async function finish() {
  if (done) staff.apply(done)
  await router.push('/')
}
</script>

<template>
  <div class="si-bg"><section class="si"><div class="si-form"><div class="si-in">
    <span class="rs-eyebrow">{{ t('adm.enrol.eyebrow') }}</span>
    <template v-if="!recovery">
      <h1>{{ t('adm.enrol.titleLead') }} <em>{{ t('adm.enrol.titleEm') }}</em></h1>
      <p class="bs-mute" style="margin: 0">{{ t('adm.enrol.lede') }}</p>
      <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
      <template v-if="secret">
        <div v-if="qr" class="adm-qr" data-testid="enrol-qr" role="img" :aria-label="t('adm.enrol.qrLabel')" v-html="qr" />
        <div class="rs-field">
          <span class="rs-label">{{ t('adm.enrol.secret') }}</span>
          <code data-testid="enrol-secret" style="font-size: var(--text-lg); letter-spacing: 0.08em; overflow-wrap: anywhere">{{ grouped }}</code>
          <small class="bs-mute">{{ t('adm.enrol.secretHint') }}</small>
          <a :href="uri" style="font-size: var(--text-sm)">{{ t('adm.enrol.open') }}</a>
        </div>
        <form style="display: grid; gap: 14px" novalidate @submit.prevent="confirm">
          <AppField v-model="code" :label="t('adm.enrol.code')" autocomplete="one-time-code" />
          <AppButton icon="shield" type="submit" size="lg" block :loading="busy" :disabled="!code">{{ busy ? t('adm.enrol.busy') : t('adm.enrol.submit') }}</AppButton>
        </form>
      </template>
    </template>
    <template v-else>
      <h1>{{ t('adm.enrol.recoveryLead') }} <em>{{ t('adm.enrol.recoveryEm') }}</em></h1>
      <p class="bs-mute" style="margin: 0">{{ t('adm.enrol.recoveryText') }}</p>
      <ul data-testid="recovery-codes" style="list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; font-family: var(--font-mono, monospace)">
        <li v-for="c in recovery" :key="c">{{ c }}</li>
      </ul>
      <AppButton icon="circle-check" size="lg" block @click="finish">{{ t('adm.enrol.recoveryDone') }}</AppButton>
    </template>
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

<style scoped>
.adm-qr { width: 200px; max-width: 100%; padding: 8px; border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: #fff; }
.adm-qr :deep(svg) { display: block; width: 100%; height: auto; }
</style>
