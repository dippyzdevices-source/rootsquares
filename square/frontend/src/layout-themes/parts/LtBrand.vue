<script setup lang="ts">
import { computed } from 'vue'
import SiteName from '../../components/ui/SiteName.vue'
import SquareMark from '../../components/ui/SquareMark.vue'
import { useSiteData } from '../useSiteData'

// The square's mark and name (and its name in its own language when it set one), linking home. `size` is the name's font size in pixels; `mark` shows
// the logo or letter mark beside it (its height follows the name unless `markSize` says otherwise).
const props = defineProps<{ size?: number; markSize?: number; mark?: boolean; onDark?: boolean; plain?: boolean }>()
const { home } = useSiteData()
const markPx = computed(() => props.markSize ?? Math.min(44, Math.max(28, Math.round((props.size ?? 22) * 1.5))))
</script>

<template>
  <router-link to="/" class="lt-brand">
    <SquareMark v-if="mark" :size="markPx" :on-dark="onDark" />
    <span class="lt-brand-text">
      <SiteName :variant="plain ? 'plain' : home.name_style" :on-dark="onDark" class="lt-brand-name" :style="size ? { fontSize: `${size}px` } : undefined" />
      <span v-if="home.tagline_local" class="lt-brand-local ds-bn">{{ home.tagline_local }}</span>
    </span>
  </router-link>
</template>
