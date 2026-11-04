<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseBreadcrumbs from '../../components/ui/BaseBreadcrumbs.vue'
import ImageLightbox from '../../components/ui/ImageLightbox.vue'
import { fetchAlbum, type AlbumDetail } from '../../services/galleryApi'
import { ensureMinLoadingDuration } from '../../utils/minLoadingDuration'

const route = useRoute()

const album = ref<AlbumDetail | null>(null)
const loading = ref(true)
const notFound = ref(false)
const lightboxOpen = ref(false)
const lightboxIndex = ref(0)

const imageUrls = computed(() => album.value?.media.map((photo) => photo.url) ?? [])
const currentPhoto = computed(() => album.value?.media[lightboxIndex.value] ?? null)

function openLightbox(index: number) {
  lightboxIndex.value = index
  lightboxOpen.value = true
}

onMounted(async () => {
  const startedAt = Date.now()
  try {
    album.value = await fetchAlbum(Number(route.params.id))
  } catch {
    notFound.value = true
  } finally {
    await ensureMinLoadingDuration(startedAt)
    loading.value = false
  }
})
</script>

<template>
  <div class="ds-scope">
    <section class="ds-band ds-band-wash" style="padding-bottom: var(--ds-space-6)">
      <div class="ds-container">
        <BaseBreadcrumbs
          :items="[{ label: 'Home', to: '/' }, { label: 'Gallery', to: '/gallery' }, ...(album ? [{ label: album.title }] : [])]"
          style="display: block; margin-bottom: var(--ds-space-5)"
        />

        <BaseLoadingState v-if="loading" label="Loading album…" />
        <BaseEmptyState
          v-else-if="notFound"
          title="Album not found"
          description="This album may have been removed or is no longer published."
        />
        <div v-else-if="album" class="ds-heading">
          <span v-if="album.published === false" class="ds-badge ds-badge-neutral draft-pill">Draft</span>
          <h1 class="ds-display ds-display-m">{{ album.title }}</h1>
          <p v-if="album.description" class="ds-intro ds-desc" :data-desc-style="album.description_style ?? undefined">{{ album.description }}</p>
        </div>
      </div>
    </section>

    <section v-if="album" class="ds-band ds-band-paper">
      <div class="ds-container ds-cards" style="grid-template-columns: repeat(auto-fill, minmax(min(100%, 200px), 1fr))">
        <button
          v-for="(photo, index) in album.media"
          :key="photo.id"
          type="button"
          class="ds-rect"
          style="aspect-ratio: 1"
          @click="openLightbox(index)"
        >
          <img
            :src="photo.thumbnail_url"
            :alt="photo.filename"
            loading="lazy"
            class="ds-rect-inner"
            style="object-fit: cover"
          />
        </button>
      </div>
    </section>

    <ImageLightbox
      v-if="album"
      v-model="lightboxOpen"
      v-model:index="lightboxIndex"
      :images="imageUrls"
      :alt="currentPhoto?.filename ?? album.title"
      :caption="currentPhoto?.caption"
    />
  </div>
</template>
