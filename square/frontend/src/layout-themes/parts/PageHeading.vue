<script setup lang="ts">
import type { PageHeading } from '../../services/siteContent'

// The heading of an inner page in the theme's style (W9-R5): the same words as the original band (the square's own, Settings, Content), set as the
// theme sets a section head, only larger. The slot holds extras that belong under the heading (for example the News tabs); `photo` is the About photo.
defineProps<{ heading: PageHeading; photo?: string | null }>()
</script>

<template>
  <section class="lt-pagehead">
    <div class="lt-cont">
      <div class="lt-pagehead-in" :class="{ 'lt-pagehead-photo': photo }">
        <div class="lt-stack">
          <span v-if="heading.script_line" class="lt-hand-kick">{{ heading.script_line }}</span>
          <span v-if="heading.eyebrow" class="lt-eyebrow">{{ heading.eyebrow }}</span>
          <h1 class="lt-h1 lt-pagehead-h1">{{ heading.title }}</h1>
          <p v-if="heading.local_line" class="lt-native ds-bn">{{ heading.local_line }}</p>
          <p v-if="heading.intro" class="lt-lead">{{ heading.intro }}</p>
          <slot />
        </div>
        <div v-if="photo" class="lt-pagehead-pic"><img :src="photo" alt="" loading="lazy" /></div>
      </div>
    </div>
  </section>
</template>
