<script setup lang="ts">
import BaseButton from '../../components/ui/BaseButton.vue'
import { squareProfile } from '../../services/squareConfig'

// The public page of an Event pass in its archive (W11, ADR 044): the event is over. Like the back-soon page of a sleeping square it is the whole page, with no
// header or footer, because nothing of the site is served any more. The owner signs in to download the reports.
</script>

<template>
  <div class="ds-scope">
    <section class="event-over-page">
      <div class="ds-container" style="max-width: var(--ds-container-narrow); margin: 0 auto; text-align: center">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Thank you</span>
        <h1 class="ds-display ds-display-m" style="margin-top: var(--ds-space-3)">{{ squareProfile.name }} is over</h1>
        <p class="ds-intro" style="max-width: none; margin: var(--ds-space-4) auto 0">
          The event has taken place and ticket sales are closed. Thank you to everyone who came and helped.
        </p>
        <div style="margin-top: var(--ds-space-6)">
          <BaseButton to="/login" variant="secondary" size="sm">Organiser? Sign in</BaseButton>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.event-over-page {
  min-height: 100vh;
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: var(--ds-space-6, 24px);
  text-align: center;
  background: var(--ds-surface-page);
}
</style>
