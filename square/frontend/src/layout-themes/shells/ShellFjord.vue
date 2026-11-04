<script setup lang="ts">
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import ThemeFooter from '../ThemeFooter.vue'
import LtBrand from '../parts/LtBrand.vue'
import LtButton from '../parts/LtButton.vue'
import { cta, navItems } from '../useSiteLayout'
import { useActive } from '../useShellBits'

// Fjord Modern: a sticky bar with the name, numbered pages in capitals and the main button (W9-R5).
const { isActive } = useActive()
</script>

<template>
  <div class="lt-shell lt-fjord">
    <header class="lt-fj-head">
      <div class="lt-cont lt-fj-bar">
        <LtBrand mark :size="22" />
        <nav aria-label="Main" class="lt-fj-nav">
          <router-link v-for="(n, i) in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined"><sup class="lt-mono">{{ String(i).padStart(2, '0') }}</sup>{{ n.label }}</router-link>
        </nav>
        <span class="lt-fj-right"><LtThemeToggle /><LtButton :to="cta.to">{{ cta.label }}</LtButton></span>
      </div>
    </header>
    <slot />
    <ThemeFooter />
  </div>
</template>
