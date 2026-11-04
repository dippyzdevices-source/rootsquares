<script setup lang="ts">
import NewsBlock from '../../layout-themes/sections/NewsBlock.vue'
import PageHeading from '../../layout-themes/parts/PageHeading.vue'
import { activeLayout } from '../../layout-themes/layouts'
const themed = activeLayout !== null // a layout theme sets the page heading and lists (W9-R5)
import { usePageHeading } from '../../composables/usePageHeading'
import { squareProfile } from '../../services/squareConfig'
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import MagazinesGrid from '../../components/MagazinesGrid.vue'
import { EMPTY_NEWS_BAND, loadHomeContent, type NewsBand } from '../../services/siteContent'
import { fetchNews, type NewsSummary } from '../../services/newsApi'
import { subscribeNewsletter } from '../../services/newsletterApi'
import { formatEventDate } from '../../utils/date'
import { useLookup } from '../../composables/useLookup'
import { moduleEnabled } from '../../services/modules'

// Articles | Magazines tabs, kept in ?view= so a magazine's back link and a shared link both land on
// the right tab. The router is optional so the page still mounts in isolation (tests).
const route = useRoute() as ReturnType<typeof useRoute> | undefined
const router = useRouter() as ReturnType<typeof useRouter> | undefined
// The band at the bottom is the square's own choice (W7-R5): no title = no band. The Magazines tab belongs to the Magazines module.
const band = ref<NewsBand>({ ...EMPTY_NEWS_BAND })
const view = ref<'articles' | 'magazines'>('articles')
const newsletterOn = moduleEnabled('newsletter') // W8-R15: the sign-up band is the Newsletter module's
const magazinesOn = moduleEnabled('magazines') // W8-R14: the owner's Magazines module, no longer a check-box
const wantsMagazines = () => magazinesOn && route?.query.view === 'magazines'
watch(
  () => route?.query.view,
  () => {
    view.value = wantsMagazines() ? 'magazines' : 'articles'
  },
)
function setView(next: 'articles' | 'magazines') {
  view.value = next
  void router?.replace({ query: next === 'magazines' ? { view: 'magazines' } : {} })
}

// Newsletter sign-up. Submitting the form is the consent (stated under the field).
const subscribeEmail = ref('')
const subscribing = ref(false)
const subscribeDone = ref(false)
const subscribeError = ref('')

async function handleSubscribe() {
  if (subscribing.value) return
  subscribeError.value = ''
  subscribing.value = true
  try {
    await subscribeNewsletter(subscribeEmail.value.trim())
    subscribeDone.value = true
    subscribeEmail.value = ''
  } catch (err) {
    subscribeError.value = err instanceof Error ? err.message : 'Could not subscribe right now.'
  } finally {
    subscribing.value = false
  }
}

const page = ref(1)
// 1 featured card + 6 in the 3-per-row grid below = exactly 2 full rows, matching
// EventsListView.vue's own perPage=6/2-rows pagination rhythm.
const perPage = 7

const articles = ref<NewsSummary[]>([])
const totalPages = ref(1)
const total = ref(0)
const loading = ref(true)
const error = ref(false)

const { options: newsCategories, label: categoryLabel } = useLookup('news_category')
const categoryFilters = computed(() => [{ value: '', label: 'All' }, ...newsCategories.value])
const category = ref('')

// A filtered view with no results shouldn't claim there's no news at all.
const emptyTitle = computed(() => (category.value ? `No ${categoryLabel(category.value).toLowerCase()} posts yet` : 'No news yet'))

// The backend has no search endpoint for news — this filters the already-loaded page
// client-side rather than faking a server-side search.
const query = ref('')
const visibleArticles = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return articles.value
  return articles.value.filter((a) => `${a.title} ${a.summary ?? ''}`.toLowerCase().includes(q))
})
const featured = computed(() => visibleArticles.value[0] ?? null)
const rest = computed(() => visibleArticles.value.slice(1))

async function load() {
  loading.value = true
  error.value = false
  try {
    const data = await fetchNews({ category: category.value || undefined, page: page.value, perPage })
    articles.value = data.items
    totalPages.value = data.total_pages
    total.value = data.total
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

watch(category, () => {
  page.value = 1
  load()
})
onMounted(async () => {
  band.value = (await loadHomeContent()).news_band
  view.value = wantsMagazines() ? 'magazines' : 'articles'
  load()
})

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
const heading = usePageHeading('news', () => ({ eyebrow: 'News & notices', title: 'News', intro: `Announcements and updates from ${squareProfile.name}.` }))
</script>

<template>
  <div class="ds-scope">
    <PageHeading v-if="themed" :heading="heading">
        <div v-if="magazinesOn" class="ds-tabs" role="tablist" style="margin-top: var(--ds-space-4)">
          <button type="button" role="tab" class="ds-tab" :class="{ 'ds-tab-active': view === 'articles' }" :aria-selected="view === 'articles'" @click="setView('articles')">Articles</button>
          <button type="button" role="tab" class="ds-tab tab-magazines" :class="{ 'ds-tab-active': view === 'magazines' }" :aria-selected="view === 'magazines'" @click="setView('magazines')">Magazines</button>
        </div>
    </PageHeading>
    <section v-else class="ds-band ds-band-wash" style="padding-bottom: var(--ds-space-6)">
      <div class="ds-container ds-heading">
        <span v-if="heading.script_line" class="ds-script">{{ heading.script_line }}</span>
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />{{ heading.eyebrow }}</span>
        <h1 class="ds-display ds-display-m">{{ heading.title }}</h1>
        <p v-if="heading.local_line" class="ds-bn" style="font-size: var(--ds-text-subtitle); color: var(--ds-text-muted)">{{ heading.local_line }}</p>
        <p class="ds-intro">{{ heading.intro }}</p>
        <div v-if="magazinesOn" class="ds-tabs" role="tablist" style="margin-top: var(--ds-space-4)">
          <button type="button" role="tab" class="ds-tab" :class="{ 'ds-tab-active': view === 'articles' }" :aria-selected="view === 'articles'" @click="setView('articles')">Articles</button>
          <button type="button" role="tab" class="ds-tab tab-magazines" :class="{ 'ds-tab-active': view === 'magazines' }" :aria-selected="view === 'magazines'" @click="setView('magazines')">Magazines</button>
        </div>
      </div>
    </section>

    <section v-if="view === 'magazines'" class="ds-band ds-band-paper" style="padding-top: var(--ds-space-6)">
      <div class="ds-container"><MagazinesGrid /></div>
    </section>

    <section v-else class="ds-band ds-band-paper" style="padding-top: var(--ds-space-6)">
      <div class="ds-container" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
          <div style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap">
            <button
              v-for="opt in categoryFilters"
              :key="opt.value"
              type="button"
              class="ds-tag"
              :class="{ 'ds-tag-selected': category === opt.value }"
              @click="category = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
          <BaseSearchField v-model="query" placeholder="Search notices" style="min-width: 220px; max-width: 260px" />
        </div>

        <BaseLoadingState v-if="loading" label="Loading news…" />
        <div v-else-if="error" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
          <h3 class="ds-subtitle">Couldn't load news</h3>
          <p class="ds-meta" style="margin-top: var(--ds-space-2)">Please try again shortly.</p>
        </div>
        <div v-else-if="articles.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
          <h3 class="ds-subtitle">{{ emptyTitle }}</h3>
          <p class="ds-meta" style="margin-top: var(--ds-space-2)">Check back soon for updates.</p>
        </div>
        <div v-else-if="visibleArticles.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
          <h3 class="ds-subtitle">Nothing matches "{{ query }}"</h3>
          <p class="ds-meta" style="margin-top: var(--ds-space-2)">Try a different search.</p>
        </div>
        <template v-else>
          <NewsBlock v-if="themed" :items="visibleArticles" full />
          <router-link v-if="!themed && featured" :to="`/news/${featured.slug}`" class="ds-card ds-card-interactive" style="padding: 0; overflow: hidden; display: block">
            <div class="ds-row ds-row--half" style="gap: 0; align-items: stretch">
              <div style="position: relative; min-height: 280px; background: var(--ds-surface-sunken); background-image: var(--ds-grain); display: flex; align-items: center; justify-content: center">
                <img v-if="featured.banner_image" :src="featured.banner_image" :alt="featured.title" style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover" />
                <svg v-else width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--ds-text-faint)"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2" /><path d="M18 14h-8" /><path d="M15 18h-5" /><path d="M10 6h8v4h-8V6Z" /></svg>
              </div>
              <div style="padding: var(--ds-space-7); display: flex; flex-direction: column; justify-content: center; gap: var(--ds-space-3)">
                <div style="display: flex; align-items: center; gap: var(--ds-space-3); flex-wrap: wrap">
                  <span class="ds-badge ds-badge-primary">Latest</span>
                  <span v-if="featured.published === false" class="ds-badge ds-badge-neutral draft-pill">Draft</span>
                  <span v-if="featured.category" class="ds-badge ds-badge-neutral">{{ categoryLabel(featured.category) }}</span>
                  <span v-if="featured.published_at" class="ds-caption">{{ formatEventDate(featured.published_at) }}</span>
                </div>
                <h2 class="ds-display ds-display-s">{{ featured.title }}</h2>
                <p v-if="featured.summary" class="ds-body-l ds-desc" :data-desc-style="featured.description_style ?? undefined">{{ featured.summary }}</p>
                <p class="ds-caption">
                  <template v-if="featured.author">{{ featured.author }} · </template>{{ featured.read_minutes }} min read
                </p>
                <span class="ds-btn ds-btn-secondary ds-btn-md" style="align-self: flex-start; margin-top: var(--ds-space-2)">
                  Read more
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg>
                </span>
              </div>
            </div>
          </router-link>

          <div v-if="!themed && rest.length" class="ds-cards ds-cards--3">
            <router-link v-for="article in rest" :key="article.id" :to="`/news/${article.slug}`" class="ds-card ds-card-interactive" style="padding: 0; overflow: hidden; display: flex; flex-direction: column">
              <div style="position: relative; aspect-ratio: 16 / 9; overflow: hidden; background: var(--ds-surface-sunken); background-image: var(--ds-grain); display: flex; align-items: center; justify-content: center">
                <img v-if="article.banner_image" :src="article.banner_image" :alt="article.title" style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover" />
                <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--ds-text-faint)"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2" /><path d="M18 14h-8" /><path d="M15 18h-5" /><path d="M10 6h8v4h-8V6Z" /></svg>
              </div>
              <div style="padding: var(--ds-space-4) var(--ds-space-5) var(--ds-space-5); display: flex; flex-direction: column; gap: var(--ds-space-3); flex: 1">
                <div style="display: flex; align-items: center; gap: var(--ds-space-3)">
                  <span v-if="article.published === false" class="ds-badge ds-badge-neutral draft-pill">Draft</span>
                  <span v-if="article.category" class="ds-badge ds-badge-neutral">{{ categoryLabel(article.category) }}</span>
                  <span v-if="article.published_at" class="ds-caption">{{ formatEventDate(article.published_at) }}</span>
                </div>
                <h3 class="ds-card-title" style="margin-top: 0">{{ article.title }}</h3>
                <p v-if="article.summary" class="ds-meta ds-desc-s" :data-desc-style="article.description_style ?? undefined">{{ article.summary }}</p>
                <p class="ds-caption" style="margin-top: auto; padding-top: var(--ds-space-2)">
                  <template v-if="article.author">{{ article.author }} · </template>{{ article.read_minutes }} min read
                </p>
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
            <span class="ds-caption">Showing {{ articles.length }} of {{ total }} notices</span>
          </nav>
        </template>
      </div>
    </section>

    <section v-if="newsletterOn && band.title" class="ds-band ds-band-card" style="border-top: 1px solid var(--ds-border-hairline)">
      <div class="ds-container ds-row ds-row--split">
        <div class="ds-heading">
          <span v-if="band.eyebrow" class="ds-eyebrow"><span class="ds-eyebrow-rule" />{{ band.eyebrow }}</span>
          <h2 class="ds-display ds-display-s">{{ band.title }}</h2>
          <p v-if="band.text" class="ds-intro">{{ band.text }}</p>
        </div>
        <div v-if="subscribeDone" class="ds-alert ds-alert-success newsletter-done"><div>Almost done — we sent you an e-mail. Open it and click the link to confirm your subscription.</div></div>
        <form v-else style="display: flex; flex-direction: column; gap: var(--ds-space-2)" @submit.prevent="handleSubscribe">
          <div style="display: flex; gap: var(--ds-space-3); align-items: flex-end; flex-wrap: wrap">
            <label class="ds-field" style="flex: 1; min-width: 200px">
              <span class="ds-field-label">Email</span>
              <span class="ds-field-control" :class="{ 'ds-field-control-error': subscribeError }">
                <input v-model="subscribeEmail" type="email" required placeholder="you@example.com" class="ds-field-input" />
              </span>
            </label>
            <BaseButton type="submit" size="lg" :disabled="subscribing">{{ subscribing ? 'Subscribing…' : 'Subscribe' }}</BaseButton>
          </div>
          <span v-if="subscribeError" class="ds-field-error-text">{{ subscribeError }}</span>
          <span v-if="band.consent" class="ds-caption">{{ band.consent }}</span>
        </form>
      </div>
    </section>
  </div>
</template>
