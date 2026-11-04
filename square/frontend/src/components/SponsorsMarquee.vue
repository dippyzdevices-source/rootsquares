<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchSponsors, type Sponsor } from '../services/sponsorsApi'
import { EMPTY_HOME_CONTENT, loadHomeContent } from '../services/siteContent'

const sponsors = ref<Sponsor[]>([])
// The words above the strip are the square's own (W7-R6); empty = no heading. The strip shows whenever the square has sponsors.
const words = ref({ eyebrow: EMPTY_HOME_CONTENT.sponsors_eyebrow, title: EMPTY_HOME_CONTENT.sponsors_title })

// One "lap" repeats the list until it comfortably overfills a wide screen; the track then holds
// two identical laps and slides exactly one lap left, so the loop is seamless.
const MIN_ITEMS_PER_LAP = 8
const SECONDS_PER_ITEM = 4

const lap = computed(() => {
  if (sponsors.value.length === 0) return []
  const repeats = Math.ceil(MIN_ITEMS_PER_LAP / sponsors.value.length)
  return Array.from({ length: repeats }, () => sponsors.value).flat()
})
const track = computed(() => [...lap.value, ...lap.value])
const durationSeconds = computed(() => lap.value.length * SECONDS_PER_ITEM)

onMounted(async () => {
  const home = await loadHomeContent()
  words.value = { eyebrow: home.sponsors_eyebrow, title: home.sponsors_title }
  try {
    sponsors.value = await fetchSponsors()
  } catch {
    // Non-critical; the section simply stays hidden.
  }
})
</script>

<template>
  <section v-if="sponsors.length > 0" class="ds-band ds-band-paper sponsors-marquee" :aria-label="words.title || words.eyebrow || 'Sponsors'">
    <div class="ds-container" style="text-align: center">
      <div v-if="words.eyebrow || words.title" class="ds-heading" style="align-items: center">
        <span v-if="words.eyebrow" class="ds-eyebrow"><span class="ds-eyebrow-rule" />{{ words.eyebrow }}</span>
        <h2 v-if="words.title" class="ds-display ds-display-s">{{ words.title }}</h2>
      </div>
      <div class="sponsors-viewport">
      <ul class="sponsors-track" :style="{ animationDuration: `${durationSeconds}s` }">
        <li v-for="(sponsor, i) in track" :key="i" class="sponsors-item" :aria-hidden="i >= lap.length ? 'true' : undefined">
          <component
            :is="sponsor.website_url ? 'a' : 'span'"
            :href="sponsor.website_url ?? undefined"
            :target="sponsor.website_url ? '_blank' : undefined"
            :rel="sponsor.website_url ? 'noopener noreferrer' : undefined"
            :tabindex="i >= lap.length ? -1 : undefined"
            class="sponsors-link"
            :class="{ 'sponsors-draft': sponsor.published === false }"
            :title="sponsor.name"
          >
            <img v-if="sponsor.logo_url" :src="sponsor.logo_url" :alt="sponsor.name" loading="lazy" class="sponsors-logo" />
            <span v-else class="sponsors-name">{{ sponsor.name }}</span>
          </component>
        </li>
      </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.sponsors-marquee {
  overflow: hidden;
}
.sponsors-viewport {
  margin-top: var(--ds-space-6);
  overflow: hidden;
  mask-image: linear-gradient(to right, transparent, #000 8%, #000 92%, transparent);
}
.sponsors-track {
  display: flex;
  width: max-content;
  margin: 0;
  padding: 0;
  list-style: none;
  animation: sponsors-scroll linear infinite;
}
.sponsors-viewport:hover .sponsors-track {
  animation-play-state: paused;
}
.sponsors-item {
  flex: none;
  padding: 0 var(--ds-space-6);
}
.sponsors-link {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 72px;
  min-width: 120px;
  color: var(--ds-text-muted, inherit);
  text-decoration: none;
}
.sponsors-logo {
  max-height: 100%;
  max-width: 180px;
  object-fit: contain;
  filter: grayscale(1);
  opacity: 0.75;
  transition: filter 0.2s, opacity 0.2s;
}
.sponsors-link:hover .sponsors-logo,
.sponsors-link:focus-visible .sponsors-logo {
  filter: none;
  opacity: 1;
}
.sponsors-name {
  font-weight: 600;
}
.sponsors-draft {
  outline: 1px dashed var(--ds-border-hairline);
}
@keyframes sponsors-scroll {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}
@media (prefers-reduced-motion: reduce) {
  .sponsors-viewport {
    mask-image: none;
    overflow-x: auto;
  }
  .sponsors-track {
    animation: none;
  }
}
</style>
