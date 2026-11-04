<script setup lang="ts">
import ThemeFooter from '../ThemeFooter.vue'
import LtAccount from '../parts/LtAccount.vue'
import LtBrand from '../parts/LtBrand.vue'
import LtButton from '../parts/LtButton.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import { activeLayout } from '../layouts'
import { cta, medium, navItems, wide } from '../useSiteLayout'
import { useActive } from '../useShellBits'
import { squareProfile } from '../../services/squareConfig'

// The bar shell of Canopy Grove, Sage Café, Verdeo and Japandi Atelier (W9-R9): a sticky bar with the name, the pages and the main button. Options of
// the theme: pill navigation (the current page on a filled pill) or an underline, capitals, and a centred masthead (Japandi). Under 1100 px the links
// tighten and the button goes.
const layout = activeLayout!
const { isActive } = useActive()
</script>

<template>
  <div class="lt-shell lt-bar" :class="{ 'lt-bar-pill': layout.nav === 'pill', 'lt-bar-up': layout.nc === 'uppercase', 'lt-bar-center': layout.hb === 'center' }">
    <header class="lt-bar-head">
      <div class="lt-cont">
        <div v-if="layout.hb === 'center'" class="lt-bar-mast">
          <span class="lt-bar-tools"><LtAccount short /><LtThemeToggle /></span>
          <router-link to="/" class="lt-bar-name">{{ squareProfile.name }}</router-link>
          <nav aria-label="Main" class="lt-bar-nav">
            <router-link v-for="n in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
          </nav>
        </div>
        <div v-else class="lt-bar-row" :class="{ 'is-medium': medium }">
          <LtBrand mark :size="24" />
          <nav aria-label="Main" class="lt-bar-nav">
            <router-link v-for="n in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
          </nav>
          <span class="lt-bar-right"><LtAccount short /><LtThemeToggle /><LtButton v-if="!medium && (layout.nc !== 'uppercase' || wide)" :to="cta.to" :kind="(layout.hbk as 'p') ?? 'p'">{{ cta.label }}</LtButton></span>
        </div>
      </div>
    </header>
    <slot />
    <ThemeFooter />
  </div>
</template>
