<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import { useAuthStore } from '@/stores/auth'
import { errorText } from './errorText'

// Onboarding for a user who signed in through the identity provider and has no organisation yet (POST /organizations).
const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const name = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await auth.createOrganization(name.value)
    await router.push('/squares/new')
  } catch (e) {
    error.value = errorText(t, e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="mk-sec"><div class="au-col">
    <header style="display: grid; gap: 12px">
      <h1 class="bs-d" style="font-size: 40px">{{ t('plat.org.title') }}</h1>
      <hr class="rs-rule">
      <p class="bs-lede" style="font-size: var(--text-base)">{{ t('plat.org.lede') }}</p>
    </header>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
    <form class="rs-stack" style="gap: 16px" novalidate @submit.prevent="submit">
      <AppField v-model="name" :label="t('plat.signup.org')" autocomplete="organization" />
      <div><AppButton icon="plus" type="submit" :loading="busy" :disabled="name.trim().length < 2">{{ busy ? t('plat.org.busy') : t('plat.org.submit') }}</AppButton></div>
    </form>
  </div></section>
</template>
