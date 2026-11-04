<script setup lang="ts">
import { computed } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

const props = withDefaults(defineProps<{ variant?: 'primary' | 'outline' | 'accent' | 'ghost'; to?: RouteLocationRaw; block?: boolean; disabled?: boolean; type?: 'button' | 'submit' }>(), { variant: 'primary', type: 'button' })
const cls = computed(() => ['t-btn', props.variant !== 'primary' && `t-btn--${props.variant}`, props.block && 't-btn--block'])
</script>

<template>
  <RouterLink v-if="to" :to="to" :class="cls"><slot /></RouterLink>
  <button v-else :type="type" :class="cls" :disabled="disabled"><slot /></button>
</template>
