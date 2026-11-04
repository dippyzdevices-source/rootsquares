<script setup lang="ts">
import BaseButton from '../../components/ui/BaseButton.vue'

// A page of a square that is still being built: the maintenance gate (from the bca-oslo site). A sleeping square has its own page: SleepingView.
</script>

<template>
  <div class="ds-scope">
    <section class="ds-band ds-band-paper" style="min-height: 420px; display: flex; align-items: center">
      <div class="ds-container" style="max-width: var(--ds-container-narrow); margin: 0 auto; text-align: center">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Coming soon</span>
        <h1 class="ds-display ds-display-m" style="margin-top: var(--ds-space-3)">This page is under construction</h1>
        <p class="ds-intro" style="max-width: none; margin: var(--ds-space-4) auto 0">
          We're still putting the finishing touches on this part of the site. In the meantime, here's what's ready:
        </p>
        <div style="display: flex; gap: var(--ds-space-3); justify-content: center; margin-top: var(--ds-space-6); flex-wrap: wrap">
          <BaseButton to="/events" size="lg">Available Events</BaseButton>
          <BaseButton to="/orders/lookup" variant="secondary" size="lg">Find your order</BaseButton>
        </div>
      </div>
    </section>
  </div>
</template>
