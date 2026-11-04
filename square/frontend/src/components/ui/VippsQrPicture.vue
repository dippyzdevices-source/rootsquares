<script setup lang="ts">
// The picture of the square's own Vipps QR code, shown to people who pay with Vipps QR (W16-R8). Nothing when the square has not uploaded one.
defineProps<{ src: string | null | undefined }>()
</script>

<template>
  <img v-if="src" :src="src" alt="Vipps QR code to scan with the Vipps app" class="vipps-qr-picture" style="max-width: 240px; width: 100%; height: auto; border-radius: var(--ds-radius-md, 8px)" />
</template>
