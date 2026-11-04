<script setup lang="ts">
import { useUiStore } from '@rootsquares/ui/stores/ui'
import ToastHost from '@rootsquares/ui/components/ToastHost.vue'
import EnvBanner from '@rootsquares/ui/components/EnvBanner.vue'
import { envLabel } from '@rootsquares/ui/env/envLabel'

useUiStore() // applies saved mode and locale on startup
// Which copy of rootsquares this is (W26-R25), display only: the server says it ("Staging" on Render, "Local" on a development machine, nothing in production).
</script>

<template>
  <EnvBanner :label="envLabel" />
  <RouterView />
  <ToastHost />
</template>
