<script setup lang="ts">
import GalleryBlock from '../../layout-themes/sections/GalleryBlock.vue'
import PageHeading from '../../layout-themes/parts/PageHeading.vue'
import { activeLayout } from '../../layout-themes/layouts'
const themed = activeLayout !== null // a layout theme sets the page heading and lists (W9-R5)
import { usePageHeading } from '../../composables/usePageHeading'
import { ref, computed, onMounted } from 'vue'
import { useLookup } from '../../composables/useLookup'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { fetchAlbums, fetchArchiveCoverage, type AlbumSummary, type ArchiveCoverageEra } from '../../services/galleryApi'
import { EMPTY_GALLERY_BAND, loadHomeContent, type GalleryBand } from '../../services/siteContent'
import { ensureMinLoadingDuration } from '../../utils/minLoadingDuration'

const page = ref(1)
const perPage = 12

const albums = ref<AlbumSummary[]>([])
const totalPages = ref(1)
const total = ref(0)
const loading = ref(true)
const error = ref(false)

// Real, backend-filtered categories (the admin-managed album_category list) —
// "All" is a meta-option (no category param sent), not a real value.
const { options: albumCategories } = useLookup('album_category')
const categoryFilters = computed(() => [{ value: '', label: 'All' }, ...albumCategories.value])
const activeCategory = ref('')

const sort = ref<'recent' | 'largest'>('recent')
const sortedAlbums = computed(() => {
  if (sort.value === 'largest') {
    return [...albums.value].sort((a, b) => b.photo_count - a.photo_count)
  }
  return albums.value
})

// Albums as pictures for the theme's gallery layout: the cover, the title as caption, a link to the album.
const albumItems = computed(() => sortedAlbums.value.map((a) => ({ id: a.id, filename: '', url: a.cover_thumbnail_url ?? '', thumbnail_url: a.cover_thumbnail_url ?? '', width: 0, height: 0, caption: a.title, album_id: a.id, album_title: a.title })))

function categoryLabel(category: string | null): string | null {
  return albumCategories.value.find((c) => c.value === category)?.label ?? null
}

async function load() {
  loading.value = true
  error.value = false
  const startedAt = Date.now()
  try {
    const data = await fetchAlbums(page.value, perPage, undefined, activeCategory.value || undefined)
    albums.value = data.items
    totalPages.value = data.total_pages
    total.value = data.total
  } catch {
    error.value = true
  } finally {
    await ensureMinLoadingDuration(startedAt)
    loading.value = false
  }
}

onMounted(load)

function selectCategory(value: string) {
  if (activeCategory.value === value) return
  activeCategory.value = value
  page.value = 1
  load()
}

// Mirrors the design system's own Pagination component: always show first, last, and the
// current page, filling in neighbours until `span` slots are used, collapsing gaps with "…".
function pageList(current: number, total: number, span: number): (number | string)[] {
  if (total <= span) return Array.from({ length: total }, (_, i) => i + 1)
  const out = new Set([1, total, current])
  for (let d = 1; out.size < span && d < total; d++) {
    if (current - d > 1) out.add(current - d)
    if (out.size < span && current + d < total) out.add(current + d)
  }
  const sorted = [...out].sort((a, b) => a - b)
  const withGaps: (number | string)[] = []
  sorted.forEach((n, i) => {
    if (i > 0 && n - sorted[i - 1] > 1) withGaps.push(`gap-${n}`)
    withGaps.push(n)
  })
  return withGaps
}

const pages = computed(() => pageList(page.value, totalPages.value, 5))

function goToPage(n: number) {
  if (n >= 1 && n <= totalPages.value) {
    page.value = n
    load()
  }
}

// The band at the bottom is the square's own words (W7-R4): no title = no band. The coverage list (GET /api/gallery/coverage, photos per 5-year
// era, by each album's `year`) is fetched only when the square chose it, and a failed fetch just hides it.
const band = ref<GalleryBand>({ ...EMPTY_GALLERY_BAND })
const archiveCoverage = ref<ArchiveCoverageEra[]>([])
const coverageStates = {
  none: { label: 'No photos', tone: 'danger' },
  very_few: { label: 'Very few photos', tone: 'danger' },
  partial: { label: 'Partial', tone: 'accent' },
  complete: { label: 'Complete', tone: 'success' },
}

onMounted(async () => {
  band.value = (await loadHomeContent()).gallery_band
  if (!band.value.show_coverage) return
  try {
    archiveCoverage.value = await fetchArchiveCoverage()
  } catch {
    archiveCoverage.value = []
  }
})
const heading = usePageHeading('gallery', () => ({ eyebrow: 'Archive', title: 'Photographs from our community', intro: "Every festival, every gathering — from this year's phone photos to scanned prints from years past." }))
</script>

<template>
  <div class="ds-scope">
    <PageHeading v-if="themed" :heading="heading" />
    <section v-else class="ds-band ds-band-wash" style="padding-bottom: var(--ds-space-6)">
      <div class="ds-container ds-heading">
        <span v-if="heading.script_line" class="ds-script">{{ heading.script_line }}</span>
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />{{ heading.eyebrow }}</span>
        <h1 class="ds-display ds-display-m">{{ heading.title }}</h1>
        <p v-if="heading.local_line" class="ds-bn" style="font-size: var(--ds-text-subtitle); color: var(--ds-text-muted)">{{ heading.local_line }}</p>
        <p class="ds-intro">{{ heading.intro }}</p>
      </div>
    </section>

    <section class="ds-band ds-band-paper" style="padding-top: var(--ds-space-6)">
      <div class="ds-container" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
          <div style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap">
            <button
              v-for="cat in categoryFilters"
              :key="cat.value"
              type="button"
              class="ds-tag"
              :class="{ 'ds-tag-selected': activeCategory === cat.value }"
              @click="selectCategory(cat.value)"
            >
              {{ cat.label }}
            </button>
          </div>
          <BaseSelect v-model="sort" :options="[{ value: 'recent', label: 'Most recent' }, { value: 'largest', label: 'Largest album' }]" style="min-width: 180px" />
        </div>

        <BaseLoadingState v-if="loading" label="Loading albums…" />
        <BaseEmptyState v-else-if="error" title="Couldn't load the gallery" description="Please try again shortly." />
        <div v-else-if="albums.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
          <h3 class="ds-subtitle">No albums yet</h3>
          <p class="ds-meta" style="margin-top: var(--ds-space-2)">Check back soon for photos from our events.</p>
        </div>
        <template v-else>
          <GalleryBlock v-if="themed" :items="albumItems" :count="albumItems.length" />
          <div v-else class="ds-cards" style="grid-template-columns: repeat(auto-fill, minmax(min(100%, 280px), 1fr))">
            <router-link v-for="album in sortedAlbums" :key="album.id" :to="`/gallery/${album.id}`" class="ds-card ds-card-interactive" style="padding: 0; overflow: hidden">
              <div style="position: relative; aspect-ratio: 4 / 3; background: var(--ds-surface-sunken); background-image: var(--ds-grain); display: flex; align-items: center; justify-content: center">
                <img
                  v-if="album.cover_thumbnail_url"
                  :src="album.cover_thumbnail_url"
                  :alt="album.title"
                  loading="lazy"
                  style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover"
                />
                <svg v-else width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--ds-text-faint)"><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="9" cy="9" r="2" /><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" /></svg>
                <span v-if="categoryLabel(album.category)" class="ds-badge ds-badge-accent" style="position: absolute; top: var(--ds-space-3); left: var(--ds-space-3)">{{ categoryLabel(album.category) }}</span>
                <span class="ds-badge ds-badge-neutral" style="position: absolute; bottom: var(--ds-space-3); right: var(--ds-space-3); background: var(--ds-glass-paper); backdrop-filter: var(--ds-blur-glass)">
                  {{ album.photo_count }} photos
                </span>
              </div>
              <div style="padding: var(--ds-space-4)">
                <span v-if="album.published === false" class="ds-badge ds-badge-neutral draft-pill">Draft</span>
                <h2 class="ds-card-title" style="margin-top: 0">{{ album.title }}</h2>
                <p v-if="album.description" class="ds-meta ds-desc-s" :data-desc-style="album.description_style ?? undefined" style="margin-top: var(--ds-space-2)">{{ album.description }}</p>
              </div>
            </router-link>
          </div>

          <nav v-if="totalPages > 1" class="ds-pagination" aria-label="Pagination">
            <div class="ds-pagination-group">
              <button class="ds-page-step" :disabled="page <= 1" aria-label="Previous page" @click="goToPage(page - 1)">← Prev</button>
              <template v-for="n in pages" :key="n">
                <span v-if="typeof n === 'string'" class="ds-page-gap" aria-hidden="true">…</span>
                <button
                  v-else
                  type="button"
                  class="ds-page-btn"
                  :class="{ 'ds-page-btn-active': n === page }"
                  :aria-current="n === page ? 'page' : undefined"
                  @click="goToPage(n)"
                >
                  {{ n }}
                </button>
              </template>
              <button class="ds-page-step" :disabled="page >= totalPages" aria-label="Next page" @click="goToPage(page + 1)">Next →</button>
            </div>
            <span class="ds-caption">Showing {{ albums.length }} of {{ total }} albums</span>
          </nav>
        </template>
      </div>
    </section>

    <section v-if="band.title" class="ds-band ds-band-hero">
      <div class="ds-container ds-row ds-row--split">
        <div class="ds-heading">
          <span v-if="band.eyebrow" class="ds-eyebrow" style="color: var(--ds-saffron-300)"><span class="ds-eyebrow-rule" style="background: var(--ds-saffron-400)" />{{ band.eyebrow }}</span>
          <h2 class="ds-display ds-display-s" style="color: var(--ds-paper-50)">{{ band.title }}</h2>
          <p v-if="band.text" class="ds-body-l" style="color: var(--ds-paper-200); max-width: 46ch">{{ band.text }}</p>
          <BaseButton v-if="band.button_label" to="/contact?reason=photos" variant="inverse" style="margin-top: var(--ds-space-5)">
            {{ band.button_label }}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 21h14" /></svg>
          </BaseButton>
        </div>
        <div v-if="band.show_coverage && archiveCoverage.length" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <div v-for="entry in archiveCoverage" :key="entry.era" style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); padding: var(--ds-space-3) 0; border-bottom: 1px solid var(--ds-border-on-dark)">
            <span style="font-family: var(--ds-font-display); font-size: var(--ds-text-subtitle); color: var(--ds-paper-50)">{{ entry.era }}</span>
            <span class="ds-badge" :class="`ds-badge-${coverageStates[entry.state].tone}`">{{ coverageStates[entry.state].label }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
