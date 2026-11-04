<script setup lang="ts">
// Status pill of the owner console pages (W11-R75): a tinted capsule with a dot. The text always says the status; the colour only helps.
withDefaults(defineProps<{ tone?: 'ok' | 'warn' | 'info' | 'bad' | 'mute'; large?: boolean }>(), { tone: 'mute' })
</script>

<template>
  <span class="oc-pill" :class="[`oc-pill--${tone}`, large && 'oc-pill--lg']"><slot /></span>
</template>
