<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { endSupportSession, onSupportMessage } from '../services/supportSession'

// The banner of a rootsquares support session (ADR 089, W23-R66): fixed at the top, never dismissible, says who is here, which parts, whether changes are allowed and
// when the access ends. It shows the last refusal or the end of the access in plain words. "End session" closes this tab's session and leaves the square's admin.
const auth = useAuthStore()
const info = computed(() => auth.user?.support ?? null)
const message = ref('')
let off: (() => void) | null = null
onMounted(() => { off = onSupportMessage((m) => (message.value = m)) })
onBeforeUnmount(() => off?.())

const PARTS: Record<string, string> = { content: 'site content', settings: 'settings and theme', health: 'health and logs', members: 'the member list (read only)' }
const parts = computed(() => (info.value?.scopes ?? []).map((s) => PARTS[s] ?? s).join(', '))
const ends = computed(() => (info.value ? new Date(info.value.ends_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : ''))

function end() {
  endSupportSession()
  window.location.assign('/')
}
</script>

<template>
  <div v-if="info" class="sup" role="status" aria-live="polite" data-testid="support-banner">
    <span class="sup__lock" aria-hidden="true">&#128274;</span>
    <span class="sup__text">
      <b>Support session by rootsquares ({{ info.name }}).</b>
      {{ info.allow_changes ? 'Changes are allowed' : 'Read only' }} · {{ parts }} · ends {{ ends }}
      <span v-if="message" class="sup__msg">{{ message }}</span>
    </span>
    <button type="button" class="sup__end" @click="end">End session</button>
  </div>
</template>

<style scoped>
.sup { position: sticky; top: 0; z-index: 2000; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 8px 16px; background: #2b1a12; color: #efe3d0; font: 500 13px/1.4 system-ui, sans-serif; }
.sup__text { flex: 1; min-width: 220px; }
.sup__msg { display: block; margin-top: 2px; color: #e0b96f; }
.sup__end { padding: 5px 14px; border: 1px solid #efe3d0; border-radius: 999px; background: transparent; color: inherit; font: 600 11px system-ui, sans-serif; letter-spacing: 0.1em; text-transform: uppercase; cursor: pointer; }
.sup__end:hover { background: #efe3d0; color: #2b1a12; }
</style>

<style>
/* A read only support session: every button that saves, sends or deletes looks switched off (the page also refuses the request, and so does the server). */
html[data-support='readonly'] button[type='submit'],
html[data-support='readonly'] [data-destructive] { opacity: 0.55; cursor: not-allowed; }
</style>
