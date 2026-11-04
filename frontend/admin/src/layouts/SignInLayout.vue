<script setup lang="ts">
import PrefControls from '@rootsquares/ui/components/PrefControls.vue'

// The light and dark switch is on the sign-in pages too (W23-R87), as it is in the console header after the sign-in.
// The frame of the three staff sign-in pages: the same wrapper the customer app puts around its sign-in (`.rs-appwrap` is the container the layouts are
// measured in, `.mk` scopes the card's centring, background and heading font), so the card looks the same. No site header or footer: staff pages hold no customer links (ADR 083).
</script>

<template>
  <div class="rs-appwrap">
    <div class="mk adm-si">
      <div class="adm-si__pref"><PrefControls /></div>
      <main id="main"><RouterView /></main>
    </div>
  </div>
</template>

<style scoped>
.adm-si { position: relative; min-height: 100vh; display: flex; flex-direction: column; background: var(--color-bg); }
.adm-si__pref { position: absolute; top: 14px; inset-inline-end: 16px; z-index: 5; }
.adm-si main { flex: 1; display: flex; flex-direction: column; }
.adm-si :deep(.si-bg) { flex: 1; }
</style>
