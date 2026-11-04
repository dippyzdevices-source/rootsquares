<script setup lang="ts">
import { computed } from 'vue'

// The one breadcrumb trail for public pages. The last item is the current page (no link); the
// item before it is offered as a "back" link on the left, and the home item ("/") is an icon.
const props = defineProps<{ items: { label: string; to?: string }[] }>()

const back = computed(() => {
  const parent = props.items.length >= 2 ? props.items[props.items.length - 2] : null
  return parent?.to ? parent : null
})
</script>

<template>
  <nav class="ds-breadcrumbs" aria-label="Breadcrumb">
    <router-link v-if="back" :to="back.to!" class="ds-breadcrumbs-back">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 18-6-6 6-6" /></svg>
      <span>{{ back.to === '/' ? 'Home' : back.label }}</span>
    </router-link>
    <ol class="ds-breadcrumbs-list">
      <li v-for="(item, i) in items" :key="i" class="ds-breadcrumbs-item" :class="{ 'ds-breadcrumbs-item--mid': i < items.length - 1 }">
        <router-link v-if="item.to && i < items.length - 1" :to="item.to" class="ds-breadcrumbs-link" :aria-label="item.to === '/' ? 'Home' : undefined">
          <svg v-if="item.to === '/'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z" /></svg>
          <template v-else>{{ item.label }}</template>
        </router-link>
        <span v-else class="ds-breadcrumbs-current" :aria-current="i === items.length - 1 ? 'page' : undefined">{{ item.label }}</span>
        <svg v-if="i < items.length - 1" class="ds-breadcrumbs-sep" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg>
      </li>
    </ol>
  </nav>
</template>
