<script setup lang="ts">
// Mirrors PageHead in design/ui_kits/console/Shell.jsx
defineProps<{ title: string }>()
</script>

<template>
  <div class="rs-row rs-between" style="gap: 12px">
    <h1 class="rs-page-title">{{ title }}</h1>
    <div class="rs-row"><slot /></div>
  </div>
</template>
