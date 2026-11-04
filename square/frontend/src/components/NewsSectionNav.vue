<script setup lang="ts">
import { computed } from 'vue'
import SectionTabs from './SectionTabs.vue'
import { moduleEnabled } from '../services/modules'

// The Magazines tab exists only when the square has the Magazines module (W8-R14; it was a check-box under Pages & media, News in W7-R5).
const tabs = computed(() => [{ to: '/admin/news', label: 'Articles' }, ...(moduleEnabled('magazines') ? [{ to: '/admin/news/magazines', label: 'Magazines' }] : [])])
</script>

<template>
  <SectionTabs :tabs="tabs" label="News sections" />
</template>
