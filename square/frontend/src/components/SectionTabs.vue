<script setup lang="ts">
// Tab strip for an admin area made of sibling pages (Members, Newsletter, ...). Exact matching on
// purpose: these are flat siblings and one path is often a prefix of another.
defineProps<{ tabs: { to: string; label: string }[]; label: string }>()
</script>

<template>
  <nav class="ds-scope ds-tabs section-tabs" :aria-label="label" style="flex-wrap: wrap; row-gap: 0">
    <router-link
      v-for="tab in tabs"
      :key="tab.to"
      :to="tab.to"
      class="ds-tab"
      style="text-decoration: none; display: inline-block"
      active-class=""
      exact-active-class="ds-tab-active"
    >
      {{ tab.label }}
    </router-link>
  </nav>
</template>
