<script setup lang="ts">
import { ref } from 'vue'
import { gateEnter } from '../services/gate'

// The passcode screen of a private (staging) deploy (W26-R20, ADR 099), shown instead of the site until the server has given this browser its pass. It is only a form:
// the gate itself is in the server. Plain wording in English (this screen is for the few people who were given the passcode), neutral colours that work in light and dark.
const passcode = ref('')
const busy = ref(false)
const error = ref('')
const MESSAGES: Record<string, string> = {
  wrong: 'That is not the passcode.',
  limited: 'Too many tries. Wait ten minutes and try again.',
  error: 'The server did not answer. Try again in a moment.',
}

async function submit() {
  error.value = ''
  busy.value = true
  const result = await gateEnter(passcode.value)
  busy.value = false
  if (result === 'ok') window.location.reload()
  else error.value = MESSAGES[result] ?? MESSAGES.error!
}
</script>

<template>
  <main class="gate">
    <form class="gate-card" novalidate data-testid="gate" @submit.prevent="submit">
      <p class="gate-eyebrow">Private</p>
      <h1>This site is private</h1>
      <p class="gate-lede">Enter the passcode you were given to continue.</p>
      <p v-if="error" class="gate-error" role="alert">{{ error }}</p>
      <label class="gate-label" for="gate-passcode">Passcode</label>
      <input id="gate-passcode" v-model="passcode" class="gate-input" type="password" autocomplete="current-password" autofocus />
      <button class="gate-button" type="submit" :disabled="!passcode || busy">{{ busy ? 'Checking...' : 'Continue' }}</button>
    </form>
  </main>
</template>

<style scoped>
.gate { min-height: 100vh; display: grid; place-items: center; padding: 32px 20px; background: Canvas; color: CanvasText; font-family: system-ui, sans-serif; }
.gate-card { width: 100%; max-width: 380px; display: grid; gap: 12px; }
.gate-eyebrow { margin: 0; font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; opacity: 0.6; }
.gate h1 { margin: 0; font-size: 30px; line-height: 1.15; font-weight: 600; }
.gate-lede { margin: 0; opacity: 0.75; }
.gate-error { margin: 0; padding: 10px 12px; border: 1px solid #b3261e; border-radius: 8px; color: #b3261e; font-size: 14px; }
.gate-label { font-size: 14px; font-weight: 600; }
.gate-input { min-height: 40px; padding: 0 12px; border: 1px solid GrayText; border-radius: 10px; font: inherit; background: Field; color: FieldText; }
.gate-input:focus-visible { outline: 2px solid Highlight; outline-offset: 1px; }
.gate-button { min-height: 44px; border: 0; border-radius: 999px; background: ButtonText; color: ButtonFace; font: 600 13px system-ui, sans-serif; letter-spacing: 0.08em; text-transform: uppercase; cursor: pointer; }
.gate-button:disabled { opacity: 0.5; cursor: not-allowed; }
.gate-button:focus-visible { outline: 2px solid Highlight; outline-offset: 2px; }
</style>
