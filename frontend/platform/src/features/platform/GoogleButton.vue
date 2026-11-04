<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import { useAuthStore } from '@/stores/auth'
import { errorText } from './errorText'

// "Continue with Google" through the identity provider (ADR 028). The browser leaves for Google and comes back to /dashboard, where the
// session is picked up; a user without an organisation is then sent to /organization/new.
defineProps<{ label: string }>()
const emit = defineEmits<{ error: [message: string] }>()
const { t } = useI18n()
const auth = useAuthStore()
const busy = ref(false)

async function go() {
  busy.value = true
  try {
    await auth.providerGoogle()
  } catch (e) {
    emit('error', errorText(t, e))
    busy.value = false
  }
}
</script>

<template>
  <AppButton variant="secondary" block type="button" :loading="busy" @click="go">
    <svg width="17" height="17" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.5l6.8-6.8C35.6 2.4 30.2 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.2C12.4 13.6 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.1 24.6c0-1.6-.1-2.8-.4-4.1H24v8.4h12.5c-.3 2.1-1.6 5.2-4.6 7.3l7.7 6c4.6-4.3 6.5-10.4 6.5-17.6z" />
      <path fill="#FBBC05" d="M10.5 28.6a14.6 14.6 0 0 1 0-9.2l-7.9-6.2a24 24 0 0 0 0 21.6l7.9-6.2z" />
      <path fill="#34A853" d="M24 48c6.2 0 11.5-2 15.6-5.8l-7.7-6c-2.1 1.4-4.9 2.4-7.9 2.4-6.3 0-11.6-4.1-13.5-9.9l-7.9 6.2C6.5 42.6 14.6 48 24 48z" />
    </svg>
    {{ label }}
  </AppButton>
</template>
