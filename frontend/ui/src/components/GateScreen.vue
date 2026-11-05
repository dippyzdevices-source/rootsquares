<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from './AppAlert.vue'
import AppButton from './AppButton.vue'
import AppField from './AppField.vue'
import EnvBanner from './EnvBanner.vue'
import { envLabel } from '../env/envLabel'
import { gateEnter } from '../gate/gate'

// The passcode screen of a private (staging) deploy (W26-R20, ADR 099). It is shown instead of the app until the server has given this browser its pass.
// It is only a form: the gate itself is in the server, which refuses every API request without the pass. `base` is the API address the app talks to.
const props = defineProps<{ base: string }>()
const emit = defineEmits<{ open: [] }>()
const { t } = useI18n()
const passcode = ref('')
const busy = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  busy.value = true
  const result = await gateEnter(props.base, passcode.value)
  busy.value = false
  if (result === 'ok') emit('open')
  else error.value = t(`gate.${result}`)
}
</script>

<template>
  <EnvBanner :label="envLabel" />
  <main class="rs" style="min-height: 100vh; display: grid; place-items: center; padding: 32px 20px; background: var(--color-bg)">
    <section class="si-in" style="max-width: 400px" data-testid="gate">
      <span class="rs-eyebrow">{{ t('gate.eyebrow') }}</span>
      <h1 style="font: 500 34px/1.1 var(--font-display); margin: 0">{{ t('gate.title') }}</h1>
      <p class="bs-mute" style="margin: 0">{{ t('gate.lede') }}</p>
      <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
      <form style="display: grid; gap: 14px" novalidate @submit.prevent="submit">
        <AppField v-model="passcode" type="password" :label="t('gate.field')" autocomplete="current-password" />
        <AppButton icon="key" type="submit" size="lg" block :loading="busy" :disabled="!passcode">{{ busy ? t('gate.busy') : t('gate.submit') }}</AppButton>
      </form>
    </section>
  </main>
</template>
