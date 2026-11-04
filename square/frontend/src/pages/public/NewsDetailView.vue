<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import DOMPurify from 'dompurify'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseBreadcrumbs from '../../components/ui/BaseBreadcrumbs.vue'
import ImageLightbox from '../../components/ui/ImageLightbox.vue'
import { fetchNewsArticle, fetchNews, NewsNotFoundError, type NewsArticle, type NewsSummary } from '../../services/newsApi'
import { formatEventDate } from '../../utils/date'
import { useLookup } from '../../composables/useLookup'
import { setPageMeta } from '../../composables/usePageMeta'

const route = useRoute()

const article = ref<NewsArticle | null>(null)
const { label: categoryLabel } = useLookup('news_category')
const loading = ref(true)
const notFound = ref(false)
const related = ref<NewsSummary[]>([])
const linkCopied = ref(false)

// Sanitized on top of the backend's own sanitization (app/news/admin_routes.py's
// sanitize_news_content) — never trust a single layer for content that renders as real HTML.
const sanitizedContent = computed(() => DOMPurify.sanitize(article.value?.content ?? ''))

// "More photos" viewer — the shared ImageLightbox (same look as the event page's lightbox).
const lightboxIndex = ref(0)
const lightboxOpen = ref(false)
// The banner is the first photo in the viewer, followed by the "More photos" images.
const bannerOffset = computed(() => (article.value?.banner_image ? 1 : 0))
const imageUrls = computed(() => [
  ...(article.value?.banner_image ? [article.value.banner_image] : []),
  ...(article.value?.images.map((i) => i.image_url) ?? []),
])

function openLightbox(index: number) {
  lightboxIndex.value = index
  lightboxOpen.value = true
}

function copyLink() {
  navigator.clipboard?.writeText(window.location.href)
  linkCopied.value = true
  setTimeout(() => (linkCopied.value = false), 2000)
}

function printArticle() {
  window.print()
}

const emailHref = computed(() => {
  if (!article.value) return '#'
  const subject = article.value.title
  const body = `Thought you'd want to see this: ${window.location.href}`
  return `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
})

// Loads whatever slug the route currently points at. Kept separate from onMounted because
// tapping a "Keep reading" link only changes the route param — Vue Router reuses this component,
// so onMounted never fires again and the page would stay on the old article.
async function load(slug: string) {
  loading.value = true
  notFound.value = false
  article.value = null
  related.value = []
  lightboxOpen.value = false
  window.scrollTo({ top: 0 })

  try {
    article.value = await fetchNewsArticle(slug)
    setPageMeta(article.value.title, article.value.summary ?? undefined)
  } catch (err) {
    if (err instanceof NewsNotFoundError) {
      notFound.value = true
    }
  } finally {
    loading.value = false
  }

  try {
    const data = await fetchNews({ perPage: 4 })
    related.value = data.items.filter((a) => a.slug !== slug).slice(0, 3)
  } catch {
    // Related articles are non-critical — leave the section hidden on failure.
  }
}

onMounted(() => load(route.params.slug as string))

watch(
  () => route.params.slug,
  (slug, previous) => {
    if (typeof slug === 'string' && slug !== previous) load(slug)
  },
)
</script>

<template>
  <div class="ds-scope">
    <section class="ds-band ds-band-wash" style="padding-bottom: var(--ds-space-6)">
      <div class="ds-container" style="max-width: var(--ds-container-narrow); margin: 0 auto">
        <BaseBreadcrumbs
          :items="[
            { label: 'Home', to: '/' },
            { label: 'News', to: '/news' },
            ...(article?.category ? [{ label: categoryLabel(article.category), to: '/news' }] : []),
            ...(article ? [{ label: article.title }] : []),
          ]"
          style="display: block; margin-bottom: var(--ds-space-5)"
        />

        <BaseLoadingState v-if="loading" label="Loading article…" />
        <BaseEmptyState
          v-else-if="notFound"
          title="Article not found"
          description="This article may have been removed or is no longer published."
        />
        <div v-else-if="article" class="ds-heading">
          <span v-if="article.category" class="ds-badge ds-badge-accent">{{ categoryLabel(article.category) }}</span>
          <span v-if="article.published === false" class="ds-badge ds-badge-neutral draft-pill">Draft</span>
          <h1 class="ds-display ds-display-m">{{ article.title }}</h1>
          <p v-if="article.summary" class="ds-intro ds-desc" :data-desc-style="article.description_style ?? undefined">{{ article.summary }}</p>

          <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap; margin-top: var(--ds-space-4); padding-top: var(--ds-space-4); border-top: 1px solid var(--ds-border-hairline); width: 100%">
            <p class="ds-meta">
              <span v-if="article.author">{{ article.author }} · </span>
              <span v-if="article.published_at">{{ formatEventDate(article.published_at) }} · </span>
              {{ article.read_minutes }} min read
            </p>
            <div style="display: flex; gap: var(--ds-space-2)">
              <span class="ds-tooltip">
                <button type="button" class="ds-icon-btn ds-icon-btn-sm" aria-label="Copy link" title="Copy link" @click="copyLink">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" /></svg>
                </button>
                <span class="ds-tooltip-bubble">{{ linkCopied ? 'Copied!' : 'Copy link' }}</span>
              </span>
              <span class="ds-tooltip">
                <button type="button" class="ds-icon-btn ds-icon-btn-sm" aria-label="Print" title="Print" @click="printArticle">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9" /><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" /><rect x="6" y="14" width="12" height="8" /></svg>
                </button>
                <span class="ds-tooltip-bubble">Print</span>
              </span>
              <span class="ds-tooltip">
                <a :href="emailHref" class="ds-icon-btn ds-icon-btn-sm" aria-label="Email this">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2" /><path d="m22 6-10 7L2 6" /></svg>
                </a>
                <span class="ds-tooltip-bubble">Email this</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section v-if="article" class="ds-band ds-band-paper">
      <div class="ds-container" style="max-width: var(--ds-container-narrow); margin: 0 auto">
        <button
          v-if="article.banner_image"
          type="button"
          aria-label="View photo"
          style="display: block; width: 100%; margin-bottom: var(--ds-space-7); padding: 0; border: 0; background: var(--ds-surface-sunken); border-radius: var(--ds-radius-md); overflow: hidden; cursor: zoom-in"
          @click="openLightbox(0)"
        >
          <img :src="article.banner_image" :alt="article.title" style="display: block; width: 100%; height: auto; max-height: 80vh; object-fit: contain" />
        </button>

        <div class="news-content ds-body-l" v-html="sanitizedContent" />

        <div v-if="article.images.length" style="margin-top: var(--ds-space-7)">
          <h2 class="ds-subtitle" style="margin-bottom: var(--ds-space-4)">More photos</h2>
          <div class="ds-gallery-grid">
            <button
              v-for="(image, index) in article.images"
              :key="image.id"
              type="button"
              class="ds-gallery-item"
              @click="openLightbox(index + bannerOffset)"
            >
              <div class="ds-rect" style="aspect-ratio: 4 / 3">
                <img :src="image.image_url" :alt="article.title" loading="lazy" class="ds-rect-inner" style="object-fit: cover" />
              </div>
            </button>
          </div>
        </div>

        <div class="ds-motif" style="margin: var(--ds-space-8) auto var(--ds-space-6)">
          <span></span><span class="ds-motif-glyph">❖</span><span></span>
        </div>

        <BaseButton to="/news" variant="secondary">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5" /><path d="m12 19-7-7 7-7" /></svg>
          Back to news
        </BaseButton>
      </div>
    </section>

    <section v-if="related.length" class="ds-band ds-band-card" style="border-top: 1px solid var(--ds-border-hairline)">
      <div class="ds-container">
        <div class="ds-heading" style="margin-bottom: var(--ds-space-6)">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Keep reading</span>
          <h2 class="ds-display ds-display-s">More from the committee</h2>
        </div>
        <div class="ds-cards ds-cards--fill">
          <router-link v-for="item in related" :key="item.id" :to="`/news/${item.slug}`" class="ds-card ds-card-interactive" style="padding: 0; overflow: hidden">
            <div style="aspect-ratio: 16 / 9; background: var(--ds-surface-sunken); background-image: var(--ds-grain); display: flex; align-items: center; justify-content: center">
              <img v-if="item.banner_image" :src="item.banner_image" :alt="item.title" style="width: 100%; height: 100%; object-fit: cover" />
              <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--ds-text-faint)"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2" /><path d="M18 14h-8" /><path d="M15 18h-5" /><path d="M10 6h8v4h-8V6Z" /></svg>
            </div>
            <div style="padding: var(--ds-space-4) var(--ds-space-5) var(--ds-space-5)">
              <p v-if="item.published_at" class="ds-caption">{{ formatEventDate(item.published_at) }}</p>
              <h3 class="ds-card-title">{{ item.title }}</h3>
              <p v-if="item.summary" class="ds-meta ds-desc-s" :data-desc-style="item.description_style ?? undefined" style="margin-top: var(--ds-space-2)">{{ item.summary }}</p>
            </div>
          </router-link>
        </div>
      </div>
    </section>

    <ImageLightbox
      v-if="article"
      v-model="lightboxOpen"
      v-model:index="lightboxIndex"
      :images="imageUrls"
      :alt="article.title"
    />
  </div>
</template>

<style scoped>
/* Preserves line breaks in older plain-text articles written before this rich-text editor
   existed — new content's compact HTML (no stray newlines between tags) is unaffected. */
.news-content {
  white-space: pre-line;
}
.news-content :deep(h2) {
  font-family: var(--ds-font-display);
  font-size: var(--ds-text-title);
  margin: 1.5rem 0 0.5rem;
}
.news-content :deep(h3) {
  font-family: var(--ds-font-display);
  font-size: var(--ds-text-subtitle);
  margin: 1.25rem 0 0.5rem;
}
.news-content :deep(p) {
  margin: 0.75rem 0;
}
.news-content :deep(ul),
.news-content :deep(ol) {
  margin: 0.75rem 0;
  padding-left: 1.5rem;
}
.news-content :deep(ul) {
  list-style: disc;
}
.news-content :deep(ol) {
  list-style: decimal;
}
.news-content :deep(a) {
  color: var(--ds-text-primary);
  text-decoration: underline;
}
</style>
