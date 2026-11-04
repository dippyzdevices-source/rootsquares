<script setup lang="ts">
import ThemeFooter from '../ThemeFooter.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import LtAccount from '../parts/LtAccount.vue'
import LtBrand from '../parts/LtBrand.vue'
import { navItems } from '../useSiteLayout'
import { useActive } from '../useShellBits'

// Olive & Linen: a floating pill with the name and the pages, centred and sticky (W9-R5).
const { isActive } = useActive()
</script>

<template>
  <div class="lt-shell lt-olive">
    <header class="lt-ol-head">
      <div class="lt-ol-pill">
        <LtBrand mark :size="20" class="lt-ol-brand" />
        <nav aria-label="Main" class="lt-ol-nav">
          <router-link v-for="n in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
        </nav>
        <LtAccount class="lt-ol-account" /><LtThemeToggle />
      </div>
    </header>
    <slot />
    <ThemeFooter />
  </div>
</template>
