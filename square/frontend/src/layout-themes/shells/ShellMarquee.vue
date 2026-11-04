<script setup lang="ts">
import ThemeFooter from '../ThemeFooter.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import LtAccount from '../parts/LtAccount.vue'
import LtButton from '../parts/LtButton.vue'
import { cta, navItems } from '../useSiteLayout'
import { useActive } from '../useShellBits'
import { squareProfile } from '../../services/squareConfig'

// Marquee: a plain top bar with the name and the main button, and a floating dock of pages at the bottom of the window (W9-R5).
const { isActive } = useActive()
</script>

<template>
  <div class="lt-shell lt-marquee">
    <header class="lt-mq-head">
      <div class="lt-cont lt-mq-bar">
        <router-link to="/" class="lt-mq-name"><span class="lt-mq-dot" aria-hidden="true" />{{ squareProfile.name }}</router-link>
        <span class="lt-mq-right"><LtAccount /><LtThemeToggle /><LtButton :to="cta.to">{{ cta.label }}</LtButton></span>
      </div>
    </header>
    <slot />
    <ThemeFooter />
    <nav aria-label="Main" class="lt-mq-dock">
      <router-link v-for="n in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
    </nav>
  </div>
</template>
