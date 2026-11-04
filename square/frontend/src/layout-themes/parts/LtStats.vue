<script setup lang="ts">
import { useSiteData } from '../useSiteData'

// The numbers strip. The square's own figures; none set = nothing shown (rule 11 and the "stats off" option of the design).
const { home } = useSiteData()
</script>

<template>
  <div v-if="home.stats.length" class="lt-stats">
    <div v-for="s in home.stats" :key="s.label"><b>{{ s.value }}</b><span>{{ s.label }}</span></div>
  </div>
</template>
