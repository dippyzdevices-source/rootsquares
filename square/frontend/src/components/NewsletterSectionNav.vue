<script setup lang="ts">
import SectionTabs from './SectionTabs.vue'

const tabs = [
  { to: '/admin/newsletter', label: 'Subscribers' },
  { to: '/admin/newsletter/issues', label: 'Newsletters' },
]
</script>

<template>
  <SectionTabs :tabs="tabs" label="Newsletter sections" />
</template>
