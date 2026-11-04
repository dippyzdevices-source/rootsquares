<script setup lang="ts">
// Page head of the owner console pages (W11-R75): the title in the display serif, a line under it, and room at the right for a pill or buttons.
defineProps<{ title: string; sub?: string }>()
</script>

<template>
  <header class="oc-hd">
    <div>
      <h1 class="oc-h1">{{ title }}</h1>
      <p v-if="sub" class="oc-sub">{{ sub }}</p>
    </div>
    <div v-if="$slots.default" class="oc-hd__side"><slot /></div>
  </header>
</template>
