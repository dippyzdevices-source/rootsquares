<script setup lang="ts">
import { moduleEnabled, offeredPhrase } from '../../services/modules'
import { phonePrefix } from '../../utils/phone'
import { squareProfile } from '../../services/squareConfig'
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '../../components/ui/BaseButton.vue'
import { emailVerificationMode } from '../../services/authMode'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const email = ref('')
const password = ref('')
const phone = ref('')
const errorMessage = ref('')
const successMessage = ref('')
const submitting = ref(false)

// Code mode only (Neon Auth, local/test): after signing up the form is replaced by a step where
// the user types the 6-digit code emailed to them. Production (Supabase, link mode) never
// enters it and keeps the plain "check your email" message.
const step = ref<'form' | 'code'>('form')
const code = ref('')
const verifying = ref(false)
const resending = ref(false)
const resendCooldown = ref(0)
let cooldownTimer: ReturnType<typeof setInterval> | null = null

// Re-entry path (code mode only): a user who left the code step — refresh, closed tab, or a
// failed sign-in that said "Email not verified" — comes back via /register?verify=<email>.
// The code step opens with that address prefilled. No resend cooldown: they may already hold a
// valid code. In link mode, or for anything that isn't a single string containing '@', it's
// ignored and the normal form shows.
const verifyParam = route.query.verify
if (emailVerificationMode === 'code' && typeof verifyParam === 'string' && verifyParam.includes('@')) {
  email.value = verifyParam
  step.value = 'code'
}

// Accept pasted "123 456" / "123-456" — only the digits count.
const codeDigits = computed(() => code.value.replace(/\D/g, '').slice(0, 6))
const canVerify = computed(() => codeDigits.value.length === 6 && !verifying.value)

function startResendCooldown() {
  if (cooldownTimer) clearInterval(cooldownTimer)
  resendCooldown.value = 30
  cooldownTimer = setInterval(() => {
    resendCooldown.value -= 1
    if (resendCooldown.value <= 0 && cooldownTimer) {
      clearInterval(cooldownTimer)
      cooldownTimer = null
    }
  }, 1000)
}

onBeforeUnmount(() => {
  if (cooldownTimer) clearInterval(cooldownTimer)
})

const passwordStrength = computed(() => {
  const pw = password.value
  return Math.min(100, pw.length * 12 + (/[0-9]/.test(pw) ? 18 : 0) + (/[^a-zA-Z0-9]/.test(pw) ? 18 : 0))
})
const strengthLabel = computed(() => {
  if (passwordStrength.value < 34) return 'Too short'
  if (passwordStrength.value < 68) return 'Passable'
  return 'Strong'
})
const strengthTone = computed(() => {
  if (passwordStrength.value < 34) return 'primary'
  if (passwordStrength.value < 68) return 'accent'
  return 'success'
})

async function submit() {
  errorMessage.value = ''
  successMessage.value = ''
  submitting.value = true
  try {
    await auth.signUp(email.value, password.value, phone.value || undefined)
    if (emailVerificationMode === 'code') {
      step.value = 'code'
      // Found live: Neon Auth emits NO send.otp event when an account is created — only when a
      // code is explicitly requested — so without this the user would wait for an email nothing
      // asked for. Request the first code ourselves, exactly as the Resend button does.
      resending.value = true
      try {
        await auth.resendVerificationCode(email.value)
        startResendCooldown()
      } catch (err) {
        // The account exists; only the send failed. Keep the code step open and leave Resend
        // usable at once (no cooldown) so the user can simply try again.
        errorMessage.value =
          `Your account was created, but we couldn't send the code: ${err instanceof Error ? err.message : 'unknown error'}. Use "Resend code" to try again.`
      } finally {
        resending.value = false
      }
    } else {
      successMessage.value = 'Check your email to confirm your account before logging in.'
    }
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Could not register.'
  } finally {
    submitting.value = false
  }
}

async function verifyCode() {
  errorMessage.value = ''
  successMessage.value = ''
  verifying.value = true
  try {
    const signedIn = await auth.verifyEmailCode(email.value, codeDigits.value)
    await router.push(signedIn ? '/' : { path: '/login', query: { verified: '1' } })
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Could not verify that code.'
  } finally {
    verifying.value = false
  }
}

async function resendCode() {
  if (resending.value) return
  errorMessage.value = ''
  successMessage.value = ''
  resending.value = true
  try {
    await auth.resendVerificationCode(email.value)
    successMessage.value = 'We sent you a new code.'
    startResendCooldown()
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Could not resend the code.'
  } finally {
    resending.value = false
  }
}

async function registerWithGoogle() {
  errorMessage.value = ''
  try {
    await auth.signInWithGoogle()
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Could not start Google sign-up.'
  }
}
const membershipsOn = moduleEnabled('memberships')
const ticketsOn = moduleEnabled('tickets')
// What a new account is for, from what this square offers (W8-R19)
const registerLine = membershipsOn && ticketsOn ? 'Register once, then request the membership that fits you and book tickets straight from your dashboard.' : membershipsOn ? 'Register once, then request the membership that fits you straight from your dashboard.' : ticketsOn ? 'Register once, then book tickets straight from your dashboard.' : 'Register once and sign in whenever you need to.'
const offeredText = offeredPhrase() // W8-R16: only what this square offers
</script>

<template>
  <div class="ds-scope">
    <div class="ds-auth-shell">
      <aside class="ds-auth-aside">
        <span class="ds-wordmark-stack">
          <span class="ds-wordmark ds-wordmark-onDark">{{ squareProfile.name }}</span>
        </span>

        <div>
          <p class="ds-eyebrow" style="color: var(--ds-saffron-300); margin-bottom: var(--ds-space-4)">Join {{ squareProfile.name }}</p>
          <h1 class="ds-display ds-display-m" style="color: var(--ds-paper-100)">
            {{ offeredText ? `One account for ${offeredText}.` : 'One account for this site.' }}
          </h1>
          <p class="ds-body-l" style="color: rgba(249, 242, 232, 0.86); margin-top: var(--ds-space-4); max-width: 42ch">
            {{ registerLine }}
          </p>
          <div class="ds-motif ds-motif-onDark" style="max-width: none; margin: var(--ds-space-7) 0">
            <span></span><span class="ds-motif-glyph">❖</span><span></span>
          </div>
        </div>

        <span></span>
      </aside>

      <div class="ds-auth-panel">
        <div class="ds-auth-card">
          <nav class="ds-auth-tabs">
            <router-link to="/login" class="ds-auth-tab">Sign in</router-link>
            <router-link to="/register" class="ds-auth-tab ds-auth-tab-active">Register</router-link>
          </nav>

          <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-5)">
            <div>
              <h2 class="ds-title">{{ step === 'code' ? 'Verify your email' : 'Create your account' }}</h2>
              <p class="ds-meta" style="margin-top: var(--ds-space-1)">
                {{ step === 'code' ? `We sent a 6-digit code to ${email}.` : membershipsOn ? 'You can request a membership and pay after registering.' : 'Create your account to sign in.' }}
              </p>
            </div>

            <div v-if="errorMessage" class="ds-alert ds-alert-danger">
              <div>
                <strong class="ds-alert-title">Almost there</strong>
                {{ errorMessage }}
              </div>
            </div>
            <div v-if="successMessage" class="ds-alert ds-alert-success">
              <div>{{ successMessage }}</div>
            </div>

            <template v-if="step === 'form'">
<template v-if="squareProfile.googleLogin">
            <button type="button" class="ds-google-btn" @click="registerWithGoogle">
              <svg width="17" height="17" viewBox="0 0 48 48" aria-hidden="true">
                <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.5l6.8-6.8C35.6 2.4 30.2 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.2C12.4 13.6 17.7 9.5 24 9.5z" />
                <path fill="#4285F4" d="M46.1 24.6c0-1.6-.1-2.8-.4-4.1H24v8.4h12.5c-.3 2.1-1.6 5.2-4.6 7.3l7.7 6c4.6-4.3 6.5-10.4 6.5-17.6z" />
                <path fill="#FBBC05" d="M10.5 28.6a14.6 14.6 0 0 1 0-9.2l-7.9-6.2a24 24 0 0 0 0 21.6l7.9-6.2z" />
                <path fill="#34A853" d="M24 48c6.2 0 11.5-2 15.6-5.8l-7.7-6c-2.1 1.4-4.9 2.4-7.9 2.4-6.3 0-11.6-4.1-13.5-9.9l-7.9 6.2C6.5 42.6 14.6 48 24 48z" />
              </svg>
              Continue with Google
            </button>

            <div class="ds-or-rule">
              <span></span><span class="ds-or-rule-label">or</span><span></span>
            </div>
            </template>

            <label class="ds-field">
              <span class="ds-field-label">Email</span>
              <span class="ds-field-control">
                <input v-model="email" type="email" placeholder="you@example.com" class="ds-field-input" />
              </span>
              <span class="ds-field-hint">Used for sign-in, tickets, and account emails.</span>
            </label>

            <div>
              <label class="ds-field">
                <span class="ds-field-label">Choose a password</span>
                <span class="ds-field-control">
                  <input v-model="password" type="password" placeholder="At least ten characters" class="ds-field-input" />
                </span>
              </label>
              <div v-if="password" class="ds-progress-head" style="margin-top: var(--ds-space-3); margin-bottom: var(--ds-space-2)">
                <span class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow)">Strength</span>
                <span class="ds-meta">{{ strengthLabel }}</span>
              </div>
              <div v-if="password" class="ds-progress-track">
                <div
                  class="ds-progress-bar"
                  :class="`ds-progress-bar-${strengthTone}`"
                  :style="{ width: `${passwordStrength}%` }"
                ></div>
              </div>
            </div>

            <label class="ds-field">
              <span class="ds-field-label">Phone (optional)</span>
              <span class="ds-field-control">
                <input v-model="phone" type="tel" :placeholder="`${phonePrefix()}…`" class="ds-field-input" />
              </span>
            </label>

            <BaseButton type="button" size="lg" full-width :disabled="submitting" @click="submit">
              {{ submitting ? 'Registering…' : 'Create account' }}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg>
            </BaseButton>
            </template>

            <template v-else>
              <label class="ds-field">
                <span class="ds-field-label">Verification code</span>
                <span class="ds-field-control">
                  <input
                    v-model="code"
                    type="text"
                    inputmode="numeric"
                    autocomplete="one-time-code"
                    placeholder="123456"
                    class="ds-field-input code-input"
                    @keyup.enter="canVerify && verifyCode()"
                  />
                </span>
                <span class="ds-field-hint">The code expires after a few minutes.</span>
              </label>

              <BaseButton type="button" size="lg" full-width class="verify-code" :disabled="!canVerify" @click="verifyCode">
                {{ verifying ? 'Verifying…' : 'Verify email' }}
              </BaseButton>

              <button
                type="button"
                class="ds-meta resend-code"
                style="align-self: flex-start; background: none; border: none; padding: 0; color: var(--ds-text-primary); font-weight: 600; cursor: pointer"
                :disabled="resending || resendCooldown > 0"
                @click="resendCode"
              >
                {{ resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend code' }}
              </button>
            </template>

            <p v-if="step === 'form'" class="ds-meta" style="margin: 0; padding-top: var(--ds-space-4); border-top: 1px solid var(--ds-border-hairline)">
              Already registered?
              <router-link to="/login" style="color: var(--ds-text-primary); font-weight: 600">Sign in instead</router-link>.
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
