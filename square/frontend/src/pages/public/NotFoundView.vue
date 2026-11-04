<script setup lang="ts">
import BaseButton from '../../components/ui/BaseButton.vue'
</script>

<template>
  <div class="ds-scope">
    <section class="ds-band ds-band-paper" style="min-height: 420px; display: flex; align-items: center">
      <div class="ds-container" style="max-width: var(--ds-container-narrow); margin: 0 auto; text-align: center">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />404</span>
        <h1 class="ds-display ds-display-m" style="margin-top: var(--ds-space-3)">Page not found</h1>
        <p class="ds-intro" style="max-width: none; margin: var(--ds-space-4) auto 0">
          The page you're looking for doesn't exist, or may have moved. Here's what's available:
        </p>
        <div style="display: flex; gap: var(--ds-space-3); justify-content: center; margin-top: var(--ds-space-6); flex-wrap: wrap">
          <BaseButton to="/" size="lg">Go to homepage</BaseButton>
          <BaseButton to="/orders/lookup" variant="secondary" size="lg">Find your order</BaseButton>
        </div>
      </div>
    </section>
  </div>
</template>
