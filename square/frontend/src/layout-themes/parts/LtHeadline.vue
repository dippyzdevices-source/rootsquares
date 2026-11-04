<script setup lang="ts">
import { computed } from 'vue'
import { headlineParts } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import { squareProfile } from '../../services/squareConfig'

// The square's headline in three parts, the middle one emphasised (italic, or in the accent colour in the sans themes; W9-R5), under the script line when the square set one (W10-R6).
const { home } = useSiteData()
const parts = computed(() => headlineParts(home.value.headline || squareProfile.name))
</script>

<template>
  <span v-if="home.script_line" class="lt-script">{{ home.script_line }}</span>
  <h1 class="lt-h1">{{ parts[0] }} <em v-if="parts[1]">{{ parts[1] }}</em><template v-if="parts[2]">{{ ' ' }}{{ parts[2] }}</template></h1>
</template>
