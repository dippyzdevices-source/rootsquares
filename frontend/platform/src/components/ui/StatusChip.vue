<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'

// Brass chip (design/rootsquares-platform-brass/screens/A.jsx ST map): icon (12px) + text, muted status colour on a subtle fill.
// paid = success + check, pending = warning + clock, overdue = danger + alert, live = info + check, draft = dashed, no icon.
type Status = 'paid' | 'pending' | 'overdue' | 'draft' | 'live' | 'info' | 'neutral'
defineProps<{ status?: Status }>()
const MAP: Record<Status, [string, string | null]> = {
  paid: ['success', 'check'], pending: ['warning', 'clock'], overdue: ['danger', 'alert'],
  live: ['info', 'check'], draft: ['draft', null], info: ['info', 'info'], neutral: ['neutral', null],
}
</script>

<template>
  <span class="rs-chip" :class="`rs-chip--${MAP[status ?? 'neutral'][0]}`">
    <AppIcon v-if="MAP[status ?? 'neutral'][1]" :name="MAP[status ?? 'neutral'][1]!" :size="12" />
    <slot />
  </span>
</template>
