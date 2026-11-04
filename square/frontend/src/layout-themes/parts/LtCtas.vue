<script setup lang="ts">
import { cta, cta2 } from '../useSiteLayout'
import LtButton from './LtButton.vue'

// The two buttons of a hero (module rules in useSiteLayout.ts): the main one, and the second one with an arrow.
defineProps<{ dark?: boolean }>()
</script>

<template>
  <div class="lt-ctas">
    <LtButton :to="cta.to" :kind="dark ? 'w' : 'p'">{{ cta.label }}</LtButton>
    <LtButton :to="cta2.to" :kind="dark ? 'ow' : 'o'">{{ cta2.label }} →</LtButton>
  </div>
</template>
