<script setup lang="ts">
import { ref, onMounted } from 'vue'
import BaseLoadingState from './ui/BaseLoadingState.vue'
import { fetchMagazines, type Magazine } from '../services/magazinesApi'
import { formatEventDate } from '../utils/date'

const magazines = ref<Magazine[]>([])
const loading = ref(true)
const error = ref(false)

onMounted(async () => {
  try {
    magazines.value = await fetchMagazines()
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <BaseLoadingState v-if="loading" label="Loading magazines…" />
    <div v-else-if="error" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
      <h3 class="ds-subtitle">Could not load magazines</h3>
      <p class="ds-meta" style="margin-top: var(--ds-space-2)">Please try again shortly.</p>
    </div>
    <div v-else-if="magazines.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
      <h3 class="ds-subtitle">No magazines yet</h3>
      <p class="ds-meta" style="margin-top: var(--ds-space-2)">Check back soon for the next issue.</p>
    </div>
    <div v-else class="ds-gallery-grid" style="grid-template-columns: repeat(auto-fill, minmax(min(100%, 220px), 1fr))">
      <router-link v-for="magazine in magazines" :key="magazine.id" :to="`/news/magazines/${magazine.slug}`" class="ds-gallery-item magazine-card">
        <div class="ds-rect" style="aspect-ratio: 3 / 4">
          <img v-if="magazine.cover_url" :src="magazine.cover_url" :alt="magazine.title" loading="lazy" class="ds-rect-inner" style="object-fit: cover" />
          <div v-else class="ds-rect-inner ds-placeholder">{{ magazine.title }}</div>
        </div>
        <p class="ds-card-title" style="margin-top: var(--ds-space-3)">
          <span v-if="magazine.published === false" class="ds-badge ds-badge-neutral draft-pill">Draft</span>
          {{ magazine.title }}
        </p>
        <p class="ds-meta">
          <template v-if="magazine.issue_label">{{ magazine.issue_label }}</template>
          <template v-if="magazine.issue_label && magazine.issue_date"> · </template>
          <template v-if="magazine.issue_date">{{ formatEventDate(magazine.issue_date) }}</template>
        </p>
      </router-link>
    </div>
  </div>
</template>
