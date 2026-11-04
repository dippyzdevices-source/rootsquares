<script setup lang="ts">
import SiteHeader from '../components/layout/SiteHeader.vue'
import SiteFooter from '../components/layout/SiteFooter.vue'

// The original frame of the member and admin areas (header, page, footer); a square on a layout theme uses that theme's shell instead (W10-R4).
</script>

<template>
  <div class="ds-scope" style="min-height: 100%; display: flex; flex-direction: column">
    <SiteHeader />
    <slot />
    <SiteFooter />
  </div>
</template>
