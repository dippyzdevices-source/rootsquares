<script setup lang="ts">
import { computed } from 'vue'
import { activeLayout, type HeritageVariant } from '../layouts'
import { useSiteData } from '../useSiteData'
import LtPhoto from '../parts/LtPhoto.vue'

// The story in the theme's variant (W9-R5): years (a dated list), essay (photo and text with a drop cap) or stack (centred milestones). The words
// are the square's own: the About text and the timeline rows from Settings, Content. No timeline = the essay form; nothing set = no section.
const props = defineProps<{ full?: boolean; variant?: HeritageVariant }>()
const { aboutText, heritageImage, home } = useSiteData()
const shown = computed(() => home.value.about_page.timeline.slice(0, props.full ? 6 : 4))
const text = computed(() => aboutText.value.trim() || home.value.blurb.trim())
const paragraphs = computed(() => text.value.split(/\n{2,}|\r\n{2,}/).map((p) => p.trim()).filter(Boolean))
const first = computed(() => paragraphs.value[0] ?? '')
const variant = computed(() => {
  const want = props.variant ?? activeLayout!.her
  return want !== 'essay' && !shown.value.length ? 'essay' : want
})
</script>

<template>
  <div v-if="variant === 'years'" class="lt-he-years">
    <div v-for="r in shown" :key="r.year + r.title" class="lt-he-year">
      <b class="lt-he-y">{{ r.year }}</b>
      <div><strong class="lt-he-t">{{ r.title }}</strong><p v-if="r.description" class="lt-mute">{{ r.description }}</p></div>
    </div>
  </div>

  <div v-else-if="variant === 'stack'" class="lt-he-stack">
    <div v-for="r in shown" :key="r.year + r.title" class="lt-he-step">
      <span class="lt-he-pill">{{ r.year }}</span>
      <strong class="lt-he-t">{{ r.title }}</strong>
      <p v-if="r.description" class="lt-mute">{{ r.description }}</p>
    </div>
  </div>

  <div v-else class="lt-he-essay">
    <div class="lt-he-fig">
      <LtPhoto :src="heritageImage" alt="" ratio="4 / 5" />
      <p v-if="home.blurb && aboutText" class="lt-he-quote">{{ home.blurb }}</p>
    </div>
    <div class="lt-he-text">
      <p v-if="first" class="lt-he-first"><span class="lt-dropcap" aria-hidden="true">{{ first.charAt(0) }}</span><span class="lt-sr">{{ first.charAt(0) }}</span>{{ first.slice(1) }}</p>
      <p v-for="p in paragraphs.slice(1, 3)" :key="p" class="lt-mute">{{ p }}</p>
      <div v-for="r in shown" :key="r.year + r.title" class="lt-he-line"><b>{{ r.year }}</b><span class="lt-mute">{{ r.title }}<template v-if="r.description"> — {{ r.description }}</template></span></div>
    </div>
  </div>
</template>
