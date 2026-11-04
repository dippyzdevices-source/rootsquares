<script setup lang="ts">
import { computed } from 'vue'
import { squareProfile } from '../../services/squareConfig'

// The square's name in the header and footer (W6-R67). 'caps' writes it in capitals with a dot between the words, the way bca-oslo wrote BCA·OSLO;
// anything else writes it as it is. The dot takes the same colours as bca-oslo's (`ds-wordmark-dot`, or the gold one on a dark background).
const props = defineProps<{ variant?: '' | 'plain' | 'caps'; onDark?: boolean }>()
const words = computed(() => squareProfile.name.trim().split(/\s+/).filter(Boolean))
const caps = computed(() => props.variant === 'caps' && words.value.length > 1)
</script>

<template>
  <span class="ds-wordmark" :class="{ 'ds-wordmark-onDark': onDark }">
    <template v-if="caps">
      <template v-for="(word, index) in words" :key="index">
        <span v-if="index > 0" :class="onDark ? 'ds-wordmark-dot-dark' : 'ds-wordmark-dot'">·</span>{{ word.toUpperCase() }}
      </template>
    </template>
    <template v-else>{{ squareProfile.name }}</template>
  </span>
</template>
