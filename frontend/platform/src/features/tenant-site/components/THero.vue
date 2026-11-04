<script setup lang="ts">
import { useThemeLayout } from '@/components/ui/themeScope'
import TPlaceholder from './TPlaceholder.vue'

// Hero in the theme's layout: split (default), full-bleed, or text-first with stats.
defineProps<{ eyebrow: string; title: string; lead: string; stats?: { value: string; label: string }[] }>()
const layout = useThemeLayout()
</script>

<template>
  <section v-if="layout.hero === 'full'" class="t-hero--full">
    <div class="t-wrap">
      <span class="t-eyebrow">{{ eyebrow }}</span><h1>{{ title }}</h1><p class="t-lead">{{ lead }}</p>
      <div class="t-row"><slot /></div>
    </div>
  </section>
  <section v-else-if="layout.hero === 'text-first'" class="t-hero--text">
    <div class="t-wrap">
      <span class="t-eyebrow">{{ eyebrow }}</span><h1>{{ title }}</h1><p class="t-lead">{{ lead }}</p>
      <div class="t-row"><slot /></div>
      <div v-if="stats?.length" class="t-stats"><div v-for="s in stats" :key="s.label"><b>{{ s.value }}</b><span>{{ s.label }}</span></div></div>
    </div>
  </section>
  <section v-else class="t-hero">
    <div class="t-wrap t-hero__grid">
      <div class="t-hero__copy">
        <span class="t-eyebrow">{{ eyebrow }}</span><h1>{{ title }}</h1><p class="t-lead">{{ lead }}</p>
        <div class="t-row"><slot /></div>
      </div>
      <div class="t-hero__img" :style="{ maxWidth: layout.img === 'arch' ? '400px' : '560px' }">
        <TPlaceholder :ratio="layout.img === 'arch' ? '4/5' : '5/4'" label="photo · hero" />
      </div>
    </div>
  </section>
</template>
