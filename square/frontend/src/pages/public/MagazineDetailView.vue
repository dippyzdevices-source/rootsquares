<script setup lang="ts">
import { ref, watch, defineAsyncComponent, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseBreadcrumbs from '../../components/ui/BaseBreadcrumbs.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { fetchMagazine, type Magazine } from '../../services/magazinesApi'
import { formatEventDate } from '../../utils/date'

// pdf.js is heavy, so the reader is only downloaded on this page.
const PdfReader = defineAsyncComponent(() => import('../../components/ui/PdfReader.vue'))

const route = useRoute()
const router = useRouter()
const magazine = ref<Magazine | null>(null)
const loading = ref(true)
const notFound = ref(false)
const error = ref(false)

async function load(slug: string) {
  loading.value = true
  notFound.value = false
  error.value = false
  magazine.value = null
  try {
    magazine.value = await fetchMagazine(slug)
  } catch (err) {
    if ((err as Error).message === 'not_found') notFound.value = true
    else error.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => load(route.params.slug as string))
// Reused by the router when navigating between magazines, so onMounted alone is not enough.
watch(
  () => route.params.slug,
  (slug) => {
    if (slug) load(slug as string)
  },
)
</script>

<template>
  <div class="ds-scope">
    <section class="ds-band ds-band-paper" style="padding-top: var(--ds-space-6)">
      <div class="ds-container" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
        <BaseBreadcrumbs
          :items="[
            { label: 'Home', to: '/' },
            { label: 'News', to: '/news' },
            { label: 'Magazines', to: '/news?view=magazines' },
            ...(magazine ? [{ label: magazine.title }] : []),
          ]"
        />

        <BaseLoadingState v-if="loading" label="Loading magazine…" />
        <div v-else-if="notFound" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
          <h3 class="ds-subtitle">Magazine not found</h3>
          <p class="ds-meta" style="margin-top: var(--ds-space-2)">It may have been removed or is not published yet.</p>
        </div>
        <div v-else-if="error" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
          <h3 class="ds-subtitle">Could not load this magazine</h3>
          <p class="ds-meta" style="margin-top: var(--ds-space-2)">Please try again shortly.</p>
        </div>
        <template v-else-if="magazine">
          <div class="ds-heading">
            <span class="ds-eyebrow">
              <span class="ds-eyebrow-rule" />
              <span v-if="magazine.published === false" class="ds-badge ds-badge-neutral draft-pill" style="margin-right: 6px">Draft</span>
              Magazine<template v-if="magazine.issue_label"> · {{ magazine.issue_label }}</template>
            </span>
            <h1 class="ds-display ds-display-m">{{ magazine.title }}</h1>
            <p v-if="magazine.issue_date" class="ds-meta">{{ formatEventDate(magazine.issue_date) }}</p>
            <p v-if="magazine.description" class="ds-intro ds-desc" :data-desc-style="magazine.description_style ?? undefined">{{ magazine.description }}</p>
          </div>
          <PdfReader v-if="magazine.pdf_url" :url="magazine.pdf_url" :title="magazine.title" closable @close="router.push('/news?view=magazines')" />
        </template>
      </div>
    </section>
  </div>
</template>
