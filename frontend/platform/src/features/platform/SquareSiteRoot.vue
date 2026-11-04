<script setup lang="ts">
import SquareHelloView from './SquareHelloView.vue'
import { siteHost } from '@/services/hostMode'

// Root of the app when the browser is on a square's host name (see services/hostMode.ts): no platform router, stores or navigation.
// The real square site replaces SquareHelloView here later.
</script>

<template>
  <SquareHelloView :host="siteHost" />
</template>
