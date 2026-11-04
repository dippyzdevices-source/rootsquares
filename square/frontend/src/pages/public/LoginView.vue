<script setup lang="ts">
import { moduleEnabled, offeredPhrase } from '../../services/modules'
import { squareProfile } from '../../services/squareConfig'
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '../../components/ui/BaseButton.vue'
import { emailVerificationMode } from '../../services/authMode'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const justVerified = route.query.verified === '1'

const email = ref('')
const password = ref('')
const showPassword = ref(false)
const errorMessage = ref('')
const submitting = ref(false)
// Code mode only: the account exists but its email was never verified (Better Auth's "Email not
// verified"), so offer the way back into the code step instead of leaving the user stranded.
const needsVerification = ref(false)

async function submit() {
  errorMessage.value = ''
  needsVerification.value = false
  submitting.value = true
  try {
    await auth.signInWithPassword(email.value, password.value)
    router.push('/')
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Could not log in.'
    needsVerification.value = emailVerificationMode === 'code' && /not verified/i.test(errorMessage.value)
  } finally {
    submitting.value = false
  }
}

async function loginWithGoogle() {
  errorMessage.value = ''
  try {
    await auth.signInWithGoogle()
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Could not start Google login.'
  }
}
// What signing in is for, from what this square offers (W8-R19)
const membershipsOn = moduleEnabled('memberships')
const signInHeadline = membershipsOn ? `Your membership${offeredPhrase().includes('tickets') ? ', tickets, and events' : ''} — all in one place.` : 'Your account — all in one place.'
const signInLine = membershipsOn
  ? 'Sign in to manage your profile, renew your membership, and keep your details to hand.'
  : 'Sign in to manage your profile and keep your details to hand.'
</script>

<template>
  <div class="ds-scope">
    <div class="ds-auth-shell">
      <aside class="ds-auth-aside">
        <span class="ds-wordmark-stack">
          <span class="ds-wordmark ds-wordmark-onDark">{{ squareProfile.name }}</span>
        </span>

        <div>
          <p class="ds-eyebrow" style="color: var(--ds-saffron-300); margin-bottom: var(--ds-space-4)">Members' area</p>
          <h1 class="ds-display ds-display-m" style="color: var(--ds-paper-100)">
            {{ signInHeadline }}
          </h1>
          <p class="ds-body-l" style="color: rgba(249, 242, 232, 0.86); margin-top: var(--ds-space-4); max-width: 42ch">
            {{ signInLine }}
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
            <router-link to="/login" class="ds-auth-tab ds-auth-tab-active">Sign in</router-link>
            <router-link to="/register" class="ds-auth-tab">Register</router-link>
          </nav>

          <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-5)">
            <div>
              <h2 class="ds-title">Welcome back</h2>
              <p class="ds-meta" style="margin-top: var(--ds-space-1)">{{ membershipsOn ? 'Sign in with the email on your membership.' : 'Sign in with your email.' }}</p>
            </div>

            <div v-if="justVerified" class="ds-alert ds-alert-success">
              <div>Email verified — please log in.</div>
            </div>
            <div v-if="errorMessage" class="ds-alert ds-alert-danger">
              <div>
                <strong class="ds-alert-title">We could not sign you in</strong>
                {{ errorMessage }}
                <router-link
                  v-if="needsVerification"
                  :to="{ path: '/register', query: { verify: email } }"
                  style="display: block; margin-top: var(--ds-space-2); color: var(--ds-text-primary); font-weight: 600"
                >Enter your verification code</router-link>
              </div>
            </div>

<template v-if="squareProfile.googleLogin">
            <button type="button" class="ds-google-btn" @click="loginWithGoogle">
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
                <span class="ds-field-prefix">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2" /><path d="m22 6-10 7L2 6" /></svg>
                </span>
                <input v-model="email" type="email" placeholder="you@example.com" class="ds-field-input" />
              </span>
            </label>

            <div>
              <label class="ds-field">
                <span class="ds-field-label">Password</span>
                <span class="ds-field-control">
                  <span class="ds-field-prefix">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
                  </span>
                  <input v-model="password" :type="showPassword ? 'text' : 'password'" placeholder="••••••••••" class="ds-field-input" />
                </span>
              </label>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-top: var(--ds-space-3); gap: var(--ds-space-3); flex-wrap: wrap">
                <label class="ds-switch">
                  <input v-model="showPassword" type="checkbox" role="switch" />
                  <span class="ds-switch-track"><span class="ds-switch-thumb"></span></span>
                  <span class="ds-switch-label" style="font-size: var(--ds-text-body-s)">Show password</span>
                </label>
                <router-link to="/forgot-password" class="ds-body" style="font-size: var(--ds-text-body-s); color: var(--ds-text-primary)">
                  Forgotten your password?
                </router-link>
              </div>
            </div>

            <BaseButton type="button" size="lg" full-width :disabled="submitting" @click="submit">
              {{ submitting ? 'Signing in…' : 'Sign in' }}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg>
            </BaseButton>

            <p class="ds-meta" style="margin: 0; padding-top: var(--ds-space-4); border-top: 1px solid var(--ds-border-hairline)">
              No account yet?
              <router-link to="/register" style="color: var(--ds-text-primary); font-weight: 600">Create one</router-link>.
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
