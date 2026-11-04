<script setup lang="ts">
import ThemeFooter from '../ThemeFooter.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import LtAccount from '../parts/LtAccount.vue'
import { navItems } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import { useActive } from '../useShellBits'
import { squareProfile } from '../../services/squareConfig'

// Ledger: a newspaper masthead (today's date, the name in large type) and a row of section names under a double rule (W9-R5).
const { isActive } = useActive()
const { home } = useSiteData()
const today = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
</script>

<template>
  <div class="lt-shell lt-ledger">
    <div class="lt-cont">
      <header class="lt-lg-head">
        <div class="lt-lg-meta"><span>{{ home.utility_text }}</span><span>{{ today }}</span><span class="lt-lg-acc"><LtAccount /><LtThemeToggle /></span></div>
        <div class="lt-lg-mast">
          <router-link to="/" class="lt-lg-name">{{ squareProfile.name }}</router-link>
          <span v-if="home.tagline_local" class="lt-lg-local ds-bn">{{ home.tagline_local }}</span>
        </div>
        <nav aria-label="Main" class="lt-lg-nav">
          <router-link v-for="n in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
        </nav>
      </header>
    </div>
    <slot />
    <ThemeFooter />
  </div>
</template>
