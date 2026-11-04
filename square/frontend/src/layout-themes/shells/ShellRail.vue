<script setup lang="ts">
import ThemeFooter from '../ThemeFooter.vue'
import LtAccount from '../parts/LtAccount.vue'
import LtBrand from '../parts/LtBrand.vue'
import LtButton from '../parts/LtButton.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import { cta, navItems } from '../useSiteLayout'
import { useActive } from '../useShellBits'

// Sand & Teal: a pressed card as a side rail with the name, the pages and the main button (W9-R9).
const { isActive } = useActive()
</script>

<template>
  <div class="lt-shell lt-rail">
    <aside class="lt-rail-side">
      <div class="lt-rail-in">
        <div class="lt-rail-card">
          <LtBrand mark :size="23" />
          <nav aria-label="Main" class="lt-rail-nav">
            <router-link v-for="n in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
          </nav>
          <div class="lt-rail-foot">
            <LtButton :to="cta.to">{{ cta.label }}</LtButton>
            <span class="lt-rail-acc"><LtAccount /><LtThemeToggle /></span>
          </div>
        </div>
      </div>
    </aside>
    <div class="lt-rail-main">
      <slot />
      <ThemeFooter />
    </div>
  </div>
</template>
