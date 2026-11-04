<script setup lang="ts">
import ThemeFooter from '../ThemeFooter.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import LtAccount from '../parts/LtAccount.vue'
import LtBrand from '../parts/LtBrand.vue'
import LtButton from '../parts/LtButton.vue'
import { cta, navItems } from '../useSiteLayout'
import { useActive, useMenu } from '../useShellBits'

// Below 860 px every theme uses this header: the name, a Menu button and a dropdown with 44 px rows (W9-R5). Theme shells apply only above that width.
const { isActive } = useActive()
const { open, toggle } = useMenu()
</script>

<template>
  <div class="lt-shell lt-compact">
    <header class="lt-c-head">
      <div class="lt-c-bar">
        <LtBrand mark :size="22" />
        <span class="lt-c-right"><LtThemeToggle /><button type="button" class="lt-c-menu" :aria-expanded="open" aria-controls="lt-c-nav" @click="toggle">{{ open ? 'Close' : 'Menu' }}</button></span>
      </div>
      <nav v-if="open" id="lt-c-nav" class="lt-c-nav" aria-label="Main">
        <router-link v-for="n in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
        <div class="lt-c-extra"><LtAccount :menu="false" /></div>
        <LtButton :to="cta.to">{{ cta.label }}</LtButton>
      </nav>
    </header>
    <slot />
    <ThemeFooter />
  </div>
</template>
