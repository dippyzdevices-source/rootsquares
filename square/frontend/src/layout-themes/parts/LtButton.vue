<script setup lang="ts">
// The theme's button (W9-R5): p = filled, o = outline, w = white (on photos), ow = white outline, g = text link, a = the panel accent (on coloured panels, W9-R9). Wraps long labels instead of clipping.
withDefaults(defineProps<{ to: string; kind?: 'p' | 'o' | 'w' | 'ow' | 'g' | 'a' }>(), { kind: 'p' })
</script>

<template>
  <router-link :to="to" class="lt-btn" :class="`lt-btn-${kind}`"><slot /></router-link>
</template>
