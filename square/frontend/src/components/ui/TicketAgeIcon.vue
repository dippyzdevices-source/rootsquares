<script setup lang="ts">
// Tells adult / child / other ticket types apart at a glance. Decorative alongside the ticket
// name (which stays the accessible label), so it is hidden from assistive tech.
defineProps<{ category: 'adult' | 'child' | 'other'; size?: number }>()
</script>

<template>
  <span class="ticket-age-icon" aria-hidden="true" :title="category === 'adult' ? 'Adult' : category === 'child' ? 'Child' : 'Ticket'">
    <svg :width="size ?? 22" :height="size ?? 22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
      <template v-if="category === 'adult'">
        <circle cx="12" cy="7" r="3.6" />
        <path d="M8.6 6.4c.4-2 1.9-3 3.4-3s3 1 3.4 3c-1-.9-2.2-1.3-3.4-1.3s-2.4.4-3.4 1.3z" />
        <path d="M4.5 21v-2.2c0-2.6 2.2-4.3 5-4.3h5c2.8 0 5 1.7 5 4.3V21z" />
      </template>
      <template v-else-if="category === 'child'">
        <circle cx="12" cy="12.5" r="8" />
        <path d="M8.5 5.5c1-1.6 2.3-2.4 3.5-2.4s2.5.8 3.5 2.4" />
        <path d="M12 3.1c.4-.9 1.3-1.4 2.2-1.1" />
        <circle cx="9.25" cy="11.5" r=".6" fill="currentColor" />
        <circle cx="14.75" cy="11.5" r=".6" fill="currentColor" />
        <path d="M8.75 15c.8 1.3 1.9 1.9 3.25 1.9s2.45-.6 3.25-1.9" />
      </template>
      <template v-else>
        <path d="M3 9a2 2 0 0 0 0 6v2a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1v-2a2 2 0 0 1 0-6V7a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1z" />
        <path d="M13 6v12" stroke-dasharray="2 2" />
      </template>
    </svg>
  </span>
</template>

<style scoped>
.ticket-age-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--ds-accent, currentColor);
}
</style>
