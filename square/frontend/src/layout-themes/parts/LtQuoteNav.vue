<script setup lang="ts">
import { useSiteData } from '../useSiteData'

// Previous / next testimonial, as on the default home page (W10-R6); nothing when the square has fewer than two.
const { quotes, stepQuote } = useSiteData()
</script>

<template>
  <div v-if="quotes.length > 1" class="lt-qnav">
    <button type="button" aria-label="Previous testimonial" title="Previous testimonial" @click="stepQuote(-1)">‹</button>
    <button type="button" aria-label="Next testimonial" title="Next testimonial" @click="stepQuote(1)">›</button>
  </div>
</template>
