<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { unsubscribeFromMessages } from '../../services/messagesApi'

// Opening the link from the e-mail is the request (no extra click), like the newsletter's unsubscribe page. The link carries a signed token,
// so it only works for the address it was made for.
const route = useRoute()
const state = ref<'working' | 'done' | 'invalid' | 'error'>('working')

onMounted(async () => {
  const email = typeof route.query.e === 'string' ? route.query.e : ''
  const token = typeof route.query.t === 'string' ? route.query.t : ''
  if (!email || !token) {
    state.value = 'invalid'
    return
  }
  try {
    state.value = (await unsubscribeFromMessages(email, token)) ? 'done' : 'invalid'
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
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Messages</span>
          <h1 class="ds-display ds-display-s">Unsubscribe</h1>
        </div>
        <BaseLoadingState v-if="state === 'working'" label="Unsubscribing…" />
        <div v-else-if="state === 'done'" class="ds-alert ds-alert-success"><div>You're unsubscribed. You won't get any more news messages. Messages about things you booked or bought, such as an event reminder, can still reach you.</div></div>
        <div v-else-if="state === 'invalid'" class="ds-alert ds-alert-danger"><div>This unsubscribe link isn't valid.</div></div>
        <div v-else class="ds-alert ds-alert-danger"><div>Something went wrong. Please try the link again.</div></div>
      </div>
    </section>
  </div>
</template>
