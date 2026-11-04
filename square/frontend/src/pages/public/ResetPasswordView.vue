<script setup lang="ts">
import { squareProfile } from '../../services/squareConfig'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '../../components/ui/BaseButton.vue'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const password = ref('')
const errorMessage = ref('')
const submitting = ref(false)

async function submit() {
  errorMessage.value = ''
  submitting.value = true
  try {
    await auth.updatePassword(password.value)
    router.push('/login')
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Could not update password.'
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
          <h1 class="ds-display ds-display-m" style="color: var(--ds-paper-100)">Choose a new password.</h1>
          <p class="ds-body-l" style="color: rgba(249, 242, 232, 0.86); margin-top: var(--ds-space-4); max-width: 42ch">
            Pick something you haven't used here before.
          </p>
        </div>
        <span></span>
      </aside>

      <div class="ds-auth-panel">
        <div class="ds-auth-card">
          <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-5)">
            <div>
              <h2 class="ds-title">Set a new password</h2>
            </div>

            <div v-if="errorMessage" class="ds-alert ds-alert-danger"><div>{{ errorMessage }}</div></div>

            <label class="ds-field">
              <span class="ds-field-label">New password</span>
              <span class="ds-field-control">
                <input v-model="password" type="password" placeholder="At least ten characters" class="ds-field-input" />
              </span>
            </label>

            <BaseButton type="button" size="lg" full-width :disabled="submitting" @click="submit">
              {{ submitting ? 'Saving…' : 'Save new password' }}
            </BaseButton>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
