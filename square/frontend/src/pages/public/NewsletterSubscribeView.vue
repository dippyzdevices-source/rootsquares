<script setup lang="ts">
import { onMounted, ref } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import { subscribeNewsletter } from '../../services/newsletterApi'
import { EMPTY_NEWS_BAND, loadHomeContent, type NewsBand } from '../../services/siteContent'

// The newsletter sign-up page (Newsletter module, W14-R13). With the News module on, the sign-up is the band under the news list; a square that has the
// newsletter but no news has this page instead. The words are the square's own (Settings, Pages & media, Newsletter sign-up); empty = not shown.
const band = ref<NewsBand>({ ...EMPTY_NEWS_BAND })
const email = ref('')
const sending = ref(false)
const done = ref(false)
const error = ref('')

onMounted(async () => {
  band.value = (await loadHomeContent()).news_band
})

async function submit() {
  if (sending.value) return
  error.value = ''
  sending.value = true
  try {
    await subscribeNewsletter(email.value.trim())
    done.value = true
    email.value = ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not subscribe right now.'
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <div class="ds-scope">
    <div class="ds-container" style="max-width: 640px; display: flex; flex-direction: column; gap: var(--ds-space-5); padding-top: var(--ds-space-8); padding-bottom: var(--ds-space-8)">
      <div class="ds-heading">
        <span v-if="band.eyebrow" class="ds-eyebrow"><span class="ds-eyebrow-rule" />{{ band.eyebrow }}</span>
        <h1 class="ds-display ds-display-s">{{ band.title || 'Newsletter' }}</h1>
        <p v-if="band.text" class="ds-intro">{{ band.text }}</p>
      </div>
      <div v-if="done" class="ds-alert ds-alert-success newsletter-done"><div>Almost done — we sent you an e-mail. Open it and click the link to confirm your subscription.</div></div>
      <form v-else style="display: flex; flex-direction: column; gap: var(--ds-space-2)" @submit.prevent="submit">
        <div style="display: flex; gap: var(--ds-space-3); align-items: flex-end; flex-wrap: wrap">
          <label class="ds-field" style="flex: 1; min-width: 200px">
            <span class="ds-field-label">Email</span>
            <span class="ds-field-control" :class="{ 'ds-field-control-error': error }">
              <input v-model="email" type="email" required placeholder="you@example.com" class="ds-field-input" />
            </span>
          </label>
          <BaseButton type="submit" size="lg" :disabled="sending">{{ sending ? 'Subscribing…' : 'Subscribe' }}</BaseButton>
        </div>
        <span v-if="error" class="ds-field-error-text">{{ error }}</span>
        <span v-if="band.consent" class="ds-caption">{{ band.consent }}</span>
      </form>
    </div>
  </div>
</template>
