<script setup lang="ts">
import ThemeFooter from '../ThemeFooter.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import LtAccount from '../parts/LtAccount.vue'
import LtBrand from '../parts/LtBrand.vue'
import { navItems } from '../useSiteLayout'
import { useActive } from '../useShellBits'

// Pencil Club: lined notebook paper, the name with a handwritten note, pages as slightly tilted tabs (W9-R5).
const { isActive } = useActive()
</script>

<template>
  <div class="lt-shell lt-pencil">
    <div class="lt-cont">
      <header class="lt-pc-head">
        <div class="lt-pc-top"><LtBrand mark :size="34" /><span class="lt-pc-right"><LtAccount class="lt-hand-link" /><LtThemeToggle /></span></div>
        <nav aria-label="Main" class="lt-pc-tabs">
          <router-link v-for="(n, i) in navItems" :key="n.key" :to="n.to" class="lt-pc-tab" :class="[`lt-tilt-${i % 4}`, { 'is-active': isActive(n.to) }]" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
        </nav>
      </header>
    </div>
    <slot />
    <ThemeFooter />
  </div>
</template>
