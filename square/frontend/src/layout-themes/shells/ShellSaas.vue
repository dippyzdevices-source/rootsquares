<script setup lang="ts">
import { computed } from 'vue'
import ThemeFooter from '../ThemeFooter.vue'
import LtAccount from '../parts/LtAccount.vue'
import LtBrand from '../parts/LtBrand.vue'
import LtButton from '../parts/LtButton.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import { cta, medium, navItems } from '../useSiteLayout'
import { useActive } from '../useShellBits'

// Product: an application-style header (white bar, page links with an underline) and a breadcrumb strip under it (W9-R9).
const { route, isActive } = useActive()
const here = computed(() => {
  if (route.path === '/') return 'Overview'
  const hit = navItems.find((n) => n.to !== '/' && isActive(n.to))
  return hit?.label ?? ''
})
</script>

<template>
  <div class="lt-shell lt-saas">
    <header class="lt-sa-head">
      <div class="lt-cont lt-sa-row">
        <LtBrand mark :size="20" />
        <nav aria-label="Main" class="lt-sa-nav">
          <router-link v-for="n in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
        </nav>
        <LtThemeToggle />
        <LtButton v-if="!medium" :to="cta.to">{{ cta.label }}</LtButton>
      </div>
    </header>
    <div class="lt-sa-crumb">
      <div class="lt-cont lt-sa-crumb-row">
        <router-link to="/">Home</router-link><span aria-hidden="true">/</span><span class="lt-sa-here">{{ here }}</span>
        <LtAccount class="lt-sa-acc" />
      </div>
    </div>
    <slot />
    <ThemeFooter />
  </div>
</template>
