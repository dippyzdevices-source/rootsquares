<script setup lang="ts">
import { computed } from 'vue'
import { galleryOn } from '../useSiteLayout'
import { headlineParts } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import { squareProfile } from '../../services/squareConfig'
import LtCtas from '../parts/LtCtas.vue'
import LtLead from '../parts/LtLead.vue'
import LtPhoto from '../parts/LtPhoto.vue'
import LtUpNext from '../parts/LtUpNext.vue'

// Pencil Club hero: a zine page. The middle of the headline is highlighted like a marker; photos are taped polaroids (W9-R5).
const { home, heroMain, heroThumbs } = useSiteData()
const parts = computed(() => headlineParts(home.value.headline || squareProfile.name))
</script>

<template>
  <section class="lt-hero lt-h-zine">
    <div class="lt-cont">
      <div class="lt-split lt-split-zine">
        <div class="lt-stack">
          <span v-if="home.script_line || home.eyebrow" class="lt-hand-kick">{{ home.script_line || home.eyebrow }}</span>
          <h1 class="lt-h1 lt-zine-h1">{{ parts[0] }} <em v-if="parts[1]" class="lt-marker">{{ parts[1] }}</em><template v-if="parts[2]">{{ ' ' }}{{ parts[2] }}</template></h1>
          <LtLead />
          <LtCtas />
        </div>
        <div class="lt-zine-pics">
          <div class="lt-zine-a"><LtPhoto :src="heroMain" alt="" ratio="1" radius="0" /></div>
          <span class="lt-tape lt-zine-tape" aria-hidden="true" />
          <div v-if="galleryOn" class="lt-zine-b"><LtPhoto :src="heroThumbs[0]?.thumbnail_url" alt="" ratio="1" radius="0" /></div>
          <LtUpNext v-else class="lt-zine-up" />
        </div>
      </div>
    </div>
  </section>
</template>
