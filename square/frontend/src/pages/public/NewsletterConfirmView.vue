<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { confirmNewsletter } from '../../services/newsletterApi'

// Opening the link from the e-mail is the confirmation (double opt-in): no extra click.
const route = useRoute()
const state = ref<'working' | 'done' | 'invalid' | 'error'>('working')

onMounted(async () => {
  const token = typeof route.query.token === 'string' ? route.query.token : ''
  if (!token) {
    state.value = 'invalid'
    return
  }
  try {
    state.value = (await confirmNewsletter(token)) ? 'done' : 'invalid'
  } catch {
    state.value = 'error'
  }
})
</script>

<template>
  <div class="ds-scope">
    <section class="ds-band">
      <div class="ds-container" style="max-width: 640px; display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Newsletter</span>
          <h1 class="ds-display ds-display-s">Confirm your subscription</h1>
        </div>
        <BaseLoadingState v-if="state === 'working'" label="Confirming…" />
        <div v-else-if="state === 'done'" class="ds-alert ds-alert-success">
          <div>You're subscribed — thank you. The next newsletter will reach you.</div>
        </div>
        <div v-else-if="state === 'invalid'" class="ds-alert ds-alert-danger">
          <div>This confirmation link isn't valid. If you unsubscribed since, subscribe again.</div>
        </div>
        <div v-else class="ds-alert ds-alert-danger">
          <div>Something went wrong — please try the link again.</div>
        </div>
      </div>
    </section>
  </div>
</template>
