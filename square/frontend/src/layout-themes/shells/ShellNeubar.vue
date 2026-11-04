<script setup lang="ts">
import ThemeFooter from '../ThemeFooter.vue'
import LtAccount from '../parts/LtAccount.vue'
import LtBrand from '../parts/LtBrand.vue'
import LtButton from '../parts/LtButton.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import { cta, medium, navItems } from '../useSiteLayout'
import { useActive } from '../useShellBits'

// The soft bar of Softform and Pearl (W9-R9): the pages sit in a pressed pill, the current one raised.
const { isActive } = useActive()
</script>

<template>
  <div class="lt-shell lt-neubar">
    <header class="lt-nb-head">
      <div class="lt-cont lt-nb-row">
        <LtBrand mark :size="24" />
        <nav aria-label="Main" class="lt-nb-nav">
          <router-link v-for="n in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
        </nav>
        <span class="lt-nb-right"><LtAccount short /><LtThemeToggle /><LtButton v-if="!medium" :to="cta.to">{{ cta.label }}</LtButton></span>
      </div>
    </header>
    <slot />
    <ThemeFooter />
  </div>
</template>
