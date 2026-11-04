<script setup lang="ts">
import ThemeFooter from '../ThemeFooter.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import LtAccount from '../parts/LtAccount.vue'
import LtBrand from '../parts/LtBrand.vue'
import LtButton from '../parts/LtButton.vue'
import { cta, navItems } from '../useSiteLayout'
import { useActive } from '../useShellBits'

// Harvest Hall: a sticky left sidebar with the mark, the name, the pages and the main button (W9-R5).
const { isActive } = useActive()
</script>

<template>
  <div class="lt-shell lt-sidebar">
    <aside class="lt-sb">
      <div class="lt-sb-in">
        <LtBrand mark :size="24" :mark-size="46" class="lt-sb-brand" />
        <nav aria-label="Main" class="lt-sb-nav">
          <router-link v-for="n in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
        </nav>
        <div class="lt-sb-foot">
          <LtButton :to="cta.to">{{ cta.label }}</LtButton>
          <span class="lt-sb-acc"><LtAccount /><LtThemeToggle /></span>
        </div>
      </div>
    </aside>
    <div class="lt-sb-main">
      <slot />
      <ThemeFooter />
    </div>
  </div>
</template>
