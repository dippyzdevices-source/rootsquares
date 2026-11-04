<script setup lang="ts">
import { squareProfile } from '../../services/squareConfig'

// The back-soon page of a sleeping square (Keep, W10-R41, W10-R44, W17-R24). Asleep is a state of the whole site, not a page: App.vue shows this in place of
// the router's page, at the address the visitor typed, so after the square wakes a reload simply works. The platform copied the public contact details
// when the square went to sleep (the square's own data is not available while its project is paused); an empty one is not shown.
const { email, phone, address } = squareProfile.sleepContact
</script>

<template>
  <main class="ds-scope" data-testid="sleeping-page">
    <section class="resting-page">
      <div class="ds-container" style="max-width: var(--ds-container-narrow); margin: 0 auto; text-align: center">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Back soon</span>
        <h1 class="ds-display ds-display-m" style="margin-top: var(--ds-space-3)">{{ squareProfile.name }} is taking a rest</h1>
        <p class="ds-intro" style="max-width: none; margin: var(--ds-space-4) auto 0">
          The website is resting for now and will be back soon.<template v-if="email || phone || address"> You can still reach us:</template>
        </p>
        <p v-if="email || phone || address" data-testid="resting-contact" style="margin: var(--ds-space-4) 0 0; display: grid; gap: 4px">
          <a v-if="email" :href="`mailto:${email}`">{{ email }}</a>
          <a v-if="phone" :href="`tel:${phone.replace(/\s+/g, '')}`">{{ phone }}</a>
          <span v-if="address">{{ address }}</span>
        </p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.resting-page { min-height: 100vh; min-height: 100dvh; display: grid; place-items: center; padding: var(--ds-space-6, 24px); text-align: center; background: var(--ds-surface-page); background-image: var(--ds-grain); }
.resting-page p { margin-inline: auto; }
</style>
