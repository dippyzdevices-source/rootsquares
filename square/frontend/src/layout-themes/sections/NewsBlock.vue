<script setup lang="ts">
import { computed } from 'vue'
import { useLookup } from '../../composables/useLookup'
import type { NewsSummary } from '../../services/newsApi'
import { formatEventDate } from '../../utils/date'
import { activeLayout, type NewsVariant } from '../layouts'
import LtPhoto from '../parts/LtPhoto.vue'

// Notices and announcements in the theme's variant (W9-R5): lead (one large story and a list), cols (three columns), index (a dated list) or cards.
const props = defineProps<{ items: NewsSummary[]; full?: boolean; variant?: NewsVariant }>()
const v = computed(() => props.variant ?? activeLayout!.news)
const { label: categoryLabel } = useLookup('news_category')
const when = (n: NewsSummary) => (n.published_at ? formatEventDate(n.published_at) : '')
const to = (n: NewsSummary) => `/news/${n.slug}`
</script>

<template>
  <p v-if="!items.length" class="lt-empty">No news yet. Check back soon for updates.</p>

  <div v-else-if="v === 'lead'" class="lt-ne-lead">
    <router-link :to="to(items[0]!)" class="lt-ne-main">
      <LtPhoto :src="items[0]!.banner_image" :alt="items[0]!.title" ratio="16 / 10" />
      <small class="lt-kick">{{ when(items[0]!) }}</small>
      <h3 class="lt-ne-h">{{ items[0]!.title }}</h3>
      <p v-if="items[0]!.summary" class="lt-mute">{{ items[0]!.summary }}</p>
    </router-link>
    <div class="lt-ne-side">
      <router-link v-for="n in items.slice(1)" :key="n.id" :to="to(n)" class="lt-ne-item">
        <small class="lt-kick">{{ when(n) }}</small>
        <strong class="lt-card-title">{{ n.title }}</strong>
        <span v-if="n.summary" class="lt-mute">{{ n.summary }}</span>
      </router-link>
    </div>
  </div>

  <div v-else-if="v === 'cols'" class="lt-ne-cols">
    <router-link v-for="n in full ? items : items.slice(0, 3)" :key="n.id" :to="to(n)" class="lt-ne-col">
      <small class="lt-kick">{{ when(n) }}<template v-if="n.category"> · {{ categoryLabel(n.category) }}</template></small>
      <h3 class="lt-ne-h lt-ne-h-s">{{ n.title }}</h3>
      <p v-if="n.summary" class="lt-mute">{{ n.summary }}</p>
      <span class="lt-more">Continue reading →</span>
    </router-link>
  </div>

  <div v-else-if="v === 'index'" class="lt-ne-index">
    <router-link v-for="n in items" :key="n.id" :to="to(n)" class="lt-ni-row">
      <span class="lt-mono lt-mute">{{ when(n) }}</span>
      <span><strong class="lt-ni-t">{{ n.title }}</strong><span v-if="n.summary" class="lt-mute lt-ni-s">{{ n.summary }}</span></span>
      <span class="lt-acc-i lt-only-wide" aria-hidden="true">→</span>
    </router-link>
  </div>

  <div v-else class="lt-ne-cards">
    <router-link v-for="n in items" :key="n.id" :to="to(n)" class="lt-card">
      <LtPhoto :src="n.banner_image" :alt="n.title" ratio="16 / 9" radius="0" />
      <span class="lt-card-body">
        <small class="lt-kick">{{ when(n) }}</small>
        <strong class="lt-card-title">{{ n.title }}</strong>
        <span v-if="n.summary" class="lt-mute">{{ n.summary }}</span>
      </span>
    </router-link>
  </div>
</template>
