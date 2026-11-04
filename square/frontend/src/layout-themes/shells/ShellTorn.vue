<script setup lang="ts">
import { computed } from 'vue'
import ThemeFooter from '../ThemeFooter.vue'
import LtAccount from '../parts/LtAccount.vue'
import LtButton from '../parts/LtButton.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import { cta, medium, navItems } from '../useSiteLayout'
import { tornPolygon, useActive } from '../useShellBits'
import { squareProfile } from '../../services/squareConfig'

// Torn Paper: a coloured header whose lower edge is torn on inner pages; on the home page it runs into the torn hero (W9-R9).
const { route, isActive } = useActive()
const home = computed(() => route.path === '/')
const torn = computed(() => (home.value ? undefined : tornPolygon(2.8)))
</script>

<template>
  <div class="lt-shell lt-tornshell">
    <header class="lt-tn-head" :class="{ 'lt-tn-inner': !home }" :style="torn ? { clipPath: torn } : undefined">
      <div class="lt-cont lt-tn-row" :class="{ 'is-medium': medium }">
        <router-link to="/" class="lt-tn-name">{{ squareProfile.name }}</router-link>
        <nav aria-label="Main" class="lt-tn-nav">
          <router-link v-for="n in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
        </nav>
        <span class="lt-tn-right"><LtAccount short /><LtThemeToggle /><LtButton v-if="!medium" :to="cta.to" kind="a">{{ cta.label }}</LtButton></span>
      </div>
    </header>
    <slot />
    <ThemeFooter />
  </div>
</template>
