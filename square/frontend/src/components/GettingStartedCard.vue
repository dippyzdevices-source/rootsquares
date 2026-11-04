<script setup lang="ts">
import { computed, ref } from 'vue'
import BaseButton from './ui/BaseButton.vue'
import { moduleEnabled, type ModuleKey } from '../services/modules'
import { squareProfile } from '../services/squareConfig'
import { groupLabel } from '../services/starterSuggestions'

// A short "where to begin" list on the admin dashboard, shaped by the kind of group and by the modules that are on (W14-R10). It only links to pages; it does
// not track what is done. The owner can close it for good (remembered in this browser only).
const KEY = 'rootsquares-getting-started-closed'
function readClosed(): boolean {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}
const closed = ref(readClosed())
function close() {
  closed.value = true
  try {
    localStorage.setItem(KEY, '1')
  } catch {
    /* the card simply comes back next time */
  }
}

const religious = squareProfile.groupType === 'religious'
const all: { to: string; title: string; hint: string; module?: ModuleKey }[] = [
  { to: '/admin/content/contact-details', title: 'Check your contact details', hint: 'The e-mail, phone and address people see on the Contact page.' },
  { to: '/admin/content/payments', title: 'Choose how people pay', hint: 'Switch on Vipps, bank transfer or cash and add your account details.', module: 'payments' },
  { to: '/admin/events/new', title: religious ? 'Plan your first gathering' : 'Create your first event', hint: 'Add it with a date, a place and a short description.', module: 'events' },
  { to: '/admin/donations', title: 'Set up your donate page', hint: 'Choose the suggested amounts and write a few words for your supporters.', module: 'donations' },
  { to: '/admin/messages/reminders', title: 'Add automatic reminders', hint: 'People hear about an event the day before, without you writing each time.', module: 'messages' },
  { to: '/admin/content/legal-texts', title: 'Write your privacy text', hint: 'Say what you keep about people and why. Ask someone who knows the rules where you live.' },
]
const items = computed(() => all.filter((i) => moduleEnabled(i.module)))
const kind = groupLabel()
</script>

<template>
  <section v-if="!closed" class="ds-card getting-started" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: var(--ds-space-3)">
      <div>
        <h2 class="ds-title">Where to begin</h2>
        <p class="ds-meta">{{ kind ? `A short list for a ${kind}.` : 'A short list to get your site ready.' }} Each step opens its page.</p>
      </div>
      <BaseButton type="button" variant="ghost" size="sm" class="close-getting-started" @click="close">Close</BaseButton>
    </div>
    <ol style="margin: 0; padding-left: var(--ds-space-5); display: flex; flex-direction: column; gap: var(--ds-space-2)">
      <li v-for="item in items" :key="item.to">
        <router-link :to="item.to" style="font-weight: 600">{{ item.title }}</router-link>
        <span class="ds-meta" style="display: block">{{ item.hint }}</span>
      </li>
    </ol>
  </section>
</template>
