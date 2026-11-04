<script setup lang="ts">
import ThemeFooter from '../ThemeFooter.vue'
import LtAccount from '../parts/LtAccount.vue'
import LtBrand from '../parts/LtBrand.vue'
import LtButton from '../parts/LtButton.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import { cta, navItems } from '../useSiteLayout'
import { useActive } from '../useShellBits'

// Daylight: a plain top bar with the name and the main button, and a floating dock of pages at the bottom of the window (W9-R9).
const { isActive } = useActive()
</script>

<template>
  <div class="lt-shell lt-dockshell">
    <header class="lt-dk-head">
      <div class="lt-cont lt-dk-row">
        <LtBrand mark :size="24" />
        <span class="lt-dk-right"><LtAccount short /><LtThemeToggle /><LtButton :to="cta.to">{{ cta.label }}</LtButton></span>
      </div>
    </header>
    <slot />
    <ThemeFooter />
    <nav aria-label="Main" class="lt-dk-dock">
      <router-link v-for="n in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
    </nav>
  </div>
</template>
