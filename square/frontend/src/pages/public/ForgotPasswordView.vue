<script setup lang="ts">
import { squareProfile } from '../../services/squareConfig'
import { ref } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()

const email = ref('')
const errorMessage = ref('')
const successMessage = ref('')
const submitting = ref(false)

async function submit() {
  errorMessage.value = ''
  successMessage.value = ''
  submitting.value = true
  try {
    await auth.requestPasswordReset(email.value)
    successMessage.value = 'Check your email for a password reset link.'
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Could not send reset email.'
  } finally {
    submitting.value = false
  }
}
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
          <h1 class="ds-display ds-display-m" style="color: var(--ds-paper-100)">Let's get you back in.</h1>
          <p class="ds-body-l" style="color: rgba(249, 242, 232, 0.86); margin-top: var(--ds-space-4); max-width: 42ch">
            We'll email you a secure link to choose a new password.
          </p>
        </div>
        <span></span>
      </aside>

      <div class="ds-auth-panel">
        <div class="ds-auth-card">
          <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-5)">
            <div>
              <h2 class="ds-title">Forgot password</h2>
              <p class="ds-meta" style="margin-top: var(--ds-space-1)">Enter the email on your account.</p>
            </div>

            <div v-if="errorMessage" class="ds-alert ds-alert-danger"><div>{{ errorMessage }}</div></div>
            <div v-if="successMessage" class="ds-alert ds-alert-success"><div>{{ successMessage }}</div></div>

            <label class="ds-field">
              <span class="ds-field-label">Email</span>
              <span class="ds-field-control">
                <input v-model="email" type="email" placeholder="you@example.com" class="ds-field-input" />
              </span>
            </label>

            <BaseButton type="button" size="lg" full-width :disabled="submitting" @click="submit">
              {{ submitting ? 'Sending…' : 'Send reset link' }}
            </BaseButton>

            <p class="ds-meta" style="margin: 0; padding-top: var(--ds-space-4); border-top: 1px solid var(--ds-border-hairline)">
              <router-link to="/login" style="color: var(--ds-text-primary); font-weight: 600">Back to sign in</router-link>
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
