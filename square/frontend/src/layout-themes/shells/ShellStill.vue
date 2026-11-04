<script setup lang="ts">
import { ref } from 'vue'
import ThemeFooter from '../ThemeFooter.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import LtAccount from '../parts/LtAccount.vue'
import { navItems } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import { useActive, useMenu } from '../useShellBits'
import { squareProfile } from '../../services/squareConfig'

// Stillwater: a centred name between two quiet words, and a full-screen menu that opens over the page (focus stays inside, Escape closes) (W9-R5).
const { isActive } = useActive()
const { home } = useSiteData()
const panel = ref<HTMLElement | null>(null)
const { open, toggle, close } = useMenu(panel, true)
</script>

<template>
  <div class="lt-shell lt-still">
    <header class="lt-still-head">
      <span class="lt-still-side">{{ home.utility_text }}</span>
      <router-link to="/" class="lt-still-name">{{ squareProfile.name }}</router-link>
      <span class="lt-still-side lt-still-right"><LtThemeToggle /><button type="button" class="lt-still-btn" :aria-expanded="open" aria-controls="lt-still-menu" @click="toggle">{{ open ? 'Close' : 'Menu' }}</button></span>
    </header>
    <div v-if="open" id="lt-still-menu" ref="panel" class="lt-still-overlay" role="dialog" aria-modal="true" aria-label="Menu">
      <button type="button" class="lt-still-btn lt-still-close" @click="close">Close</button>
      <nav aria-label="Main" class="lt-still-nav">
        <router-link v-for="n in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
      </nav>
      <LtAccount />
      <p v-if="home.tagline_local" class="lt-native ds-bn">{{ home.tagline_local }}</p>
    </div>
    <slot />
    <ThemeFooter />
  </div>
</template>
