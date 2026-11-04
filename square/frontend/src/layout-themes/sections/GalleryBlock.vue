<script setup lang="ts">
import { computed } from 'vue'
import type { GalleryMediaItem } from '../../services/galleryApi'
import { activeLayout, type GalleryVariant } from '../layouts'
import LtPhoto from '../parts/LtPhoto.vue'

// The photo archive in the theme's variant (W9-R5): masonry, mosaic, film, polaroid, uniform or feature. Real photos, alt text from the caption.
const props = defineProps<{ items: GalleryMediaItem[]; count: number; variant?: GalleryVariant }>()
const v = computed(() => props.variant ?? activeLayout!.gal)
const shown = computed(() => props.items.slice(0, props.count))
const caption = (m: GalleryMediaItem) => m.caption || m.album_title
const RATIOS = ['1.3', '0.8', '1', '1.5', '0.9', '1.2', '1', '0.75', '1.4']
const SPANS = [[2, 2], [1, 1], [1, 2], [1, 1], [2, 1], [1, 1], [1, 1], [1, 1], [2, 1]]
const TILTS = [-3, 2, -1, 3, -2, 1.5, -2.5, 2.5, -1]
const to = (m: GalleryMediaItem) => `/gallery/${m.album_id}`
</script>

<template>
  <p v-if="!shown.length" class="lt-empty">No photos yet. Check back after the next event.</p>

  <div v-else-if="v === 'masonry'" class="lt-ga-masonry">
    <router-link v-for="(m, i) in shown" :key="m.id" :to="to(m)"><LtPhoto :src="m.thumbnail_url" :alt="caption(m)" :ratio="RATIOS[i % 9]" /></router-link>
  </div>

  <div v-else-if="v === 'mosaic'" class="lt-ga-mosaic">
    <router-link v-for="(m, i) in shown" :key="m.id" :to="to(m)" class="lt-mo-cell" :style="{ '--c': SPANS[i % 9]![0], '--r': SPANS[i % 9]![1] }">
      <LtPhoto :src="m.thumbnail_url" :alt="caption(m)" />
    </router-link>
  </div>

  <div v-else-if="v === 'film'" class="lt-ga-film">
    <router-link v-for="(m, i) in shown" :key="m.id" :to="to(m)" class="lt-fi-item">
      <LtPhoto :src="m.thumbnail_url" :alt="caption(m)" ratio="3 / 4" class="lt-fi-pic" />
      <span class="lt-fi-cap lt-mono"><span>{{ String(i + 1).padStart(2, '0') }}</span><span>{{ caption(m) }}</span></span>
    </router-link>
  </div>

  <div v-else-if="v === 'polaroid'" class="lt-ga-polaroid">
    <router-link v-for="(m, i) in shown" :key="m.id" :to="to(m)" class="lt-po-item" :style="{ transform: `rotate(${TILTS[i % 9]}deg)` }">
      <LtPhoto :src="m.thumbnail_url" :alt="caption(m)" ratio="1" radius="0" />
      <span class="lt-hand-n">{{ caption(m) }}</span>
    </router-link>
  </div>

  <div v-else-if="v === 'grid'" class="lt-ga-grid">
    <router-link v-for="m in shown" :key="m.id" :to="to(m)" class="lt-gg-item">
      <LtPhoto :src="m.thumbnail_url" :alt="caption(m)" ratio="1" />
      <span class="lt-gg-cap">{{ caption(m) }}</span>
    </router-link>
  </div>

  <div v-else-if="v === 'framed'" class="lt-ga-framed">
    <router-link v-for="(m, i) in shown" :key="m.id" :to="to(m)" class="lt-fr-item">
      <LtPhoto :src="m.thumbnail_url" :alt="caption(m)" :ratio="['1', '0.85', '1.1'][i % 3]" class="lt-fr-pic" />
      <span class="lt-fr-cap">{{ caption(m) }}</span>
    </router-link>
  </div>

  <div v-else-if="v === 'blob'" class="lt-ga-blob">
    <router-link v-for="(m, i) in shown" :key="m.id" :to="to(m)" class="lt-gb-item">
      <LtPhoto :src="m.thumbnail_url" :alt="caption(m)" :ratio="['1.1', '0.95', '1', '1.2'][i % 4]" :class="`lt-blob-${i % 4}`" />
      <span class="lt-gb-cap">{{ caption(m) }}</span>
    </router-link>
  </div>

  <div v-else-if="v === 'uniform'" class="lt-ga-uniform">
    <router-link v-for="(m, i) in shown" :key="m.id" :to="to(m)" class="lt-un-item">
      <LtPhoto :src="m.thumbnail_url" :alt="caption(m)" ratio="4 / 3" />
      <span class="lt-un-cap">Fig. {{ i + 1 }} — {{ caption(m) }}</span>
    </router-link>
  </div>

  <div v-else class="lt-ga-feature">
    <router-link :to="to(shown[0]!)"><LtPhoto :src="shown[0]!.thumbnail_url" :alt="caption(shown[0]!)" ratio="1 / 1" /></router-link>
    <div class="lt-fe-side">
      <router-link v-for="m in shown.slice(1, 4)" :key="m.id" :to="to(m)"><LtPhoto :src="m.thumbnail_url" :alt="caption(m)" /></router-link>
    </div>
  </div>
</template>
