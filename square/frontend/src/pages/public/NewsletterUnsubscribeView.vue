<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { unsubscribeNewsletter } from '../../services/newsletterApi'

// Opening the link from the email is the request — no extra click, matching how every
// unsubscribe link is expected to behave.
const route = useRoute()
const state = ref<'working' | 'done' | 'invalid' | 'error'>('working')

onMounted(async () => {
  const token = typeof route.query.token === 'string' ? route.query.token : ''
  if (!token) {
    state.value = 'invalid'
    return
  }
  try {
    state.value = (await unsubscribeNewsletter(token)) ? 'done' : 'invalid'
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
          <h1 class="ds-display ds-display-s">Unsubscribe</h1>
        </div>
        <BaseLoadingState v-if="state === 'working'" label="Unsubscribing…" />
        <div v-else-if="state === 'done'" class="ds-alert ds-alert-success">
          <div>You're unsubscribed — you won't get any more newsletters.</div>
        </div>
        <div v-else-if="state === 'invalid'" class="ds-alert ds-alert-danger">
          <div>This unsubscribe link isn't valid.</div>
        </div>
        <div v-else class="ds-alert ds-alert-danger">
          <div>Something went wrong — please try the link again.</div>
        </div>
      </div>
    </section>
  </div>
</template>
