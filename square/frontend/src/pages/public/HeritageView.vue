<script setup lang="ts">
import PageHeading from '../../layout-themes/parts/PageHeading.vue'
import { activeLayout } from '../../layout-themes/layouts'
const themed = activeLayout !== null // a layout theme sets the page heading and lists (W9-R5)
import { moduleEnabled } from '../../services/modules'
import { usePageHeading } from '../../composables/usePageHeading'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { squareProfile } from '../../services/squareConfig'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import { fetchSettings } from '../../services/settingsApi'
import { fetchFounders, type Founder } from '../../services/foundersApi'
import { EMPTY_ABOUT_PAGE, loadHomeContent, type AboutPage } from '../../services/siteContent'

// Page title/meta description come from this route's `meta` in router/index.ts.
// bca-oslo's own story (its history, timeline, founders and festivals) was removed in the square app (rootsquares W6-R41): the square shows who
// it is, its hero photo and its own About text (both set by an admin in Settings, Content; W6-R58).
const heroPhotoSrc = ref<string | null>(null)
const aboutText = ref('')
const hasText = computed(() => aboutText.value.trim().length > 0)
// The sections under the About text are the square's own words (W7-R10); each shows only when it has something. Founder quotes come from the Founders
// list (Content, Founders); a failed fetch or an empty list just leaves that part out.
const about = ref<AboutPage>({ ...EMPTY_ABOUT_PAGE })
const founders = ref<Founder[]>([])
const founderIndex = ref(0)
let founderTimer: ReturnType<typeof setInterval> | null = null
const currentFounder = computed(() => founders.value[founderIndex.value] ?? null)
const showWhat = computed(() => !!(about.value.what_title || about.value.what_text))
const showValues = computed(() => about.value.values.length > 0)
const showInvolve = computed(() => !!(about.value.involve_title || about.value.involve_text))
const showFounderRow = computed(() => founders.value.length > 0 || showInvolve.value)
function showNextFounder() {
  if (founders.value.length) founderIndex.value = (founderIndex.value + 1) % founders.value.length
}
function showPreviousFounder() {
  if (founders.value.length) founderIndex.value = (founderIndex.value - 1 + founders.value.length) % founders.value.length
}
onUnmounted(() => {
  if (founderTimer) clearInterval(founderTimer)
})
const heading = usePageHeading('heritage', () => ({ eyebrow: 'About', title: `About ${squareProfile.name}`, intro: hasText.value ? '' : `${squareProfile.name} has not added its story to this page yet.` }))
onMounted(async () => {
  void loadHomeContent().then((content) => (about.value = content.about_page))
  try {
    const settings = await fetchSettings()
    heroPhotoSrc.value = settings.heritage_image_url ?? null
    aboutText.value = settings.about_text ?? ''
  } catch {
    heroPhotoSrc.value = null // the page reads fine without a photo
  }
  if (moduleEnabled('founders')) {
    // W8-R13: a square without the Founders module has no founders part and does not ask for founders
    try {
      founders.value = await fetchFounders()
    } catch {
      founders.value = []
    }
  }
  if (founders.value.length > 1) founderTimer = setInterval(showNextFounder, 7000)
})
</script>

<template>
  <div class="ds-scope">
    <PageHeading v-if="themed" :heading="heading" :photo="heroPhotoSrc" />
    <section v-else class="ds-band ds-band-hero" style="padding: var(--ds-space-8) 0">
      <div class="ds-container ds-row ds-row--half">
        <div class="ds-heading">
          <span v-if="heading.script_line" class="ds-script">{{ heading.script_line }}</span>
          <span class="ds-eyebrow" style="color: var(--ds-saffron-300)"><span class="ds-eyebrow-rule" style="background: var(--ds-saffron-400)" />{{ heading.eyebrow }}</span>
          <h1 class="ds-display ds-display-l" style="color: var(--ds-paper-50)">{{ heading.title }}</h1>
          <p v-if="heading.local_line" class="ds-bn" style="font-size: var(--ds-text-subtitle); color: var(--ds-paper-200)">{{ heading.local_line }}</p>
          <p v-if="heading.intro" class="ds-body-l" style="color: var(--ds-paper-200); max-width: 52ch">{{ heading.intro }}</p>
        </div>
        <div v-if="heroPhotoSrc" class="ds-arch" style="aspect-ratio: 16 / 11">
          <img :src="heroPhotoSrc" :alt="squareProfile.name" class="ds-arch-inner" style="object-fit: cover" />
        </div>
      </div>
    </section>
    <section v-if="hasText" class="ds-band ds-band-paper">
      <div class="ds-container ds-body-l" style="max-width: var(--ds-container-narrow); margin: 0 auto">
        <div data-testid="about-text" style="white-space: pre-wrap">{{ aboutText.trim() }}</div>
      </div>
    </section>

    <section v-if="showValues" class="ds-band ds-band-paper">
      <div class="ds-container" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
        <div v-if="about.values_title || about.values_button" style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
          <h2 v-if="about.values_title" class="ds-title">{{ about.values_title }}</h2>
          <BaseButton v-if="about.values_button && moduleEnabled('committee')" to="/committee" variant="secondary">{{ about.values_button }}</BaseButton>
        </div>
        <div class="ds-cards">
          <div v-for="value in about.values" :key="value.title" class="ds-card">
            <h3 class="ds-card-title" style="margin-top: 0">{{ value.title }}</h3>
            <p v-if="value.description" class="ds-meta" style="margin-top: var(--ds-space-2)">{{ value.description }}</p>
          </div>
        </div>
      </div>
    </section>

    <section v-if="showWhat" class="ds-band ds-band-card">
      <div class="ds-container" style="max-width: var(--ds-container-narrow); margin: 0 auto; display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <h2 v-if="about.what_title" class="ds-title">{{ about.what_title }}</h2>
        <p v-if="about.what_text" class="ds-body" style="white-space: pre-wrap">{{ about.what_text }}</p>
        <p v-if="(about.what_membership_link && moduleEnabled('memberships')) || about.what_events_link" class="ds-body">
          <router-link v-if="about.what_membership_link && moduleEnabled('memberships')" to="/membership" style="color: var(--ds-text-primary); font-weight: 600">{{ about.what_membership_link }}</router-link>
          <template v-if="about.what_membership_link && about.what_events_link"> · </template>
          <router-link v-if="about.what_events_link" to="/events" style="color: var(--ds-text-primary); font-weight: 600">{{ about.what_events_link }}</router-link>
        </p>
      </div>
    </section>

    <section v-if="about.timeline.length" class="ds-band ds-band-paper">
      <div class="ds-container">
        <span v-if="about.timeline_eyebrow" class="ds-eyebrow"><span class="ds-eyebrow-rule" />{{ about.timeline_eyebrow }}</span>
        <h2 v-if="about.timeline_title" class="ds-display ds-display-s" style="margin-top: var(--ds-space-3)">{{ about.timeline_title }}</h2>
        <div style="margin-top: var(--ds-space-6)">
          <div v-for="(entry, i) in about.timeline" :key="i" class="ds-deflist" style="padding: var(--ds-space-5) 0; border-top: 1px solid var(--ds-border-hairline)">
            <div class="ds-title" style="color: var(--ds-text-primary)">{{ entry.year }}</div>
            <div>
              <div class="ds-subtitle">{{ entry.title }}</div>
              <p v-if="entry.description" class="ds-body" style="margin-top: 4px">{{ entry.description }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section v-if="showFounderRow" class="ds-band ds-band-card">
      <div class="ds-container ds-row ds-row--thirds">
        <div v-if="currentFounder" class="ds-founder-col">
          <div class="ds-founder-portrait ds-arch">
            <img v-if="currentFounder.portrait_url" :src="currentFounder.portrait_url" :alt="currentFounder.name" class="ds-arch-inner" style="object-fit: cover" />
            <div v-else class="ds-arch-inner ds-placeholder"><span class="ds-placeholder-glyph">✺</span></div>
          </div>
          <div>
            <div class="ds-subtitle">{{ currentFounder.name }}</div>
            <span v-if="currentFounder.published === false" class="ds-badge ds-badge-neutral draft-pill">Draft</span>
            <p v-if="currentFounder.sub_name" class="ds-caption">{{ currentFounder.sub_name }}</p>
            <p class="ds-caption">{{ currentFounder.role }}</p>
          </div>
        </div>
        <div v-else />

        <div v-if="currentFounder" class="ds-quote-col">
          <blockquote class="ds-pullquote">
            <div class="ds-quote-viewport">
              <p>&ldquo;{{ currentFounder.quote }}&rdquo;</p>
            </div>
            <footer>
              <span class="ds-quote-rule" />
              {{ currentFounder.name }}, {{ currentFounder.role }}
            </footer>
          </blockquote>
          <div v-if="founders.length > 1" class="ds-testimonial-nav">
            <BaseIconButton label="Previous founder quote" size="sm" @click="showPreviousFounder">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
            </BaseIconButton>
            <div class="ds-testimonial-dots">
              <button
                v-for="(quote, dotIndex) in founders"
                :key="quote.id"
                type="button"
                class="ds-testimonial-dot"
                :class="{ 'ds-testimonial-dot-active': dotIndex === founderIndex }"
                :aria-label="`Go to founder quote ${dotIndex + 1}`"
                @click="founderIndex = dotIndex"
              />
            </div>
            <BaseIconButton label="Next founder quote" size="sm" @click="showNextFounder">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6" /></svg>
            </BaseIconButton>
          </div>
        </div>
        <div v-else />

        <div v-if="showInvolve" class="ds-card ds-card-sunken ds-involve-col">
          <span v-if="about.involve_badge" class="ds-badge ds-badge-info" style="margin-bottom: 10px">{{ about.involve_badge }}</span>
          <h2 v-if="about.involve_title" class="ds-title" style="margin: var(--ds-space-3) 0">{{ about.involve_title }}</h2>
          <p v-if="about.involve_text" class="ds-body">{{ about.involve_text }}</p>
          <BaseButton v-if="about.involve_button" to="/contact" variant="secondary">{{ about.involve_button }}</BaseButton>
        </div>
      </div>
    </section>
  </div>
</template>
