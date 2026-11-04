<script setup lang="ts">
import { computed } from 'vue'
import { useSiteData } from '../useSiteData'
import { offeredPhrase } from '../../services/modules'

// The lead paragraph and the headline in the community's own language (shown only when the square set them). The lead is the intro, the emphasised
// name (the default home page shows it in its script face) and the suffix; without a name it reads as before (W10-R4: the name was missing).
const { home } = useSiteData()
const fallback = computed(() => (offeredPhrase() ? `${offeredPhrase().charAt(0).toUpperCase()}${offeredPhrase().slice(1)}, all in one place.` : ''))
const intro = computed(() => (home.value.intro_name ? home.value.intro : [home.value.intro, home.value.intro_suffix].filter(Boolean).join(' ')) || (home.value.intro_name ? '' : fallback.value))
const suffix = computed(() => (home.value.intro_name ? home.value.intro_suffix : ''))
</script>

<template>
  <p v-if="home.local_line" class="lt-native ds-bn">{{ home.local_line }}</p>
  <p v-if="intro || home.intro_name" class="lt-lead">{{ intro }}<span v-if="home.intro_name" class="lt-lead-name">{{ home.intro_name }}</span><template v-if="suffix">{{ suffix }}</template></p>
</template>
