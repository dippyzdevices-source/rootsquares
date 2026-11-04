<script setup lang="ts">
import { computed } from 'vue'
import ThemeFooter from '../ThemeFooter.vue'
import LtAccount from '../parts/LtAccount.vue'
import SquareMark from '../../components/ui/SquareMark.vue'
import LtBrand from '../parts/LtBrand.vue'
import LtButton from '../parts/LtButton.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import { activeLayout } from '../layouts'
import { cta, navItems } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import { useActive } from '../useShellBits'
import { squareProfile } from '../../services/squareConfig'

// The six navigation shells of the engine themes (W9-R10, design/tenant-themes-v7): bar (sticky bar with pills), mast (newspaper-style masthead), tabs
// (logo row and a tab row), dock (plain top bar and a floating dock), side and right (a full-height sidebar on the left or the right). Below 1120 px
// (860 for mast, tabs and dock) LayoutShell uses the compact header instead.
const e = activeLayout!.engine!
const { isActive } = useActive()
const { home } = useSiteData()
const links = computed(() => navItems.filter((n) => n.key !== 'home'))
</script>

<template>
  <div class="lt-shell lt-eshell" :class="`lt-es-${e.shell}`">
    <aside v-if="e.shell === 'side' || e.shell === 'right'" class="lt-es-aside">
      <LtBrand mark :size="20" class="lt-es-brand" />
      <nav aria-label="Main" class="lt-es-links">
        <router-link v-for="n in links" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined"><i aria-hidden="true" />{{ n.label }}</router-link>
      </nav>
      <div class="lt-es-foot">
        <LtButton :to="cta.to" class="lt-es-full">{{ cta.label }}</LtButton>
        <div class="lt-es-foot-row"><LtAccount /><LtThemeToggle /></div>
      </div>
    </aside>

    <template v-else-if="e.shell === 'mast'">
      <header class="lt-es-mast">
        <div class="lt-cont lt-es-strip"><span class="lt-mute">{{ home.utility_text }}</span><span class="lt-es-trail"><LtAccount short /><LtButton :to="cta.to" class="lt-es-join">{{ cta.label }}</LtButton><LtThemeToggle /></span></div>
        <div class="lt-cont lt-es-masthead"><router-link to="/" class="lt-es-bigname"><SquareMark :size="44" class="lt-es-mark" />{{ squareProfile.name }}</router-link><span v-if="home.tagline_local" class="lt-brand-local ds-bn">{{ home.tagline_local }}</span></div>
        <div class="lt-es-navrow"><div class="lt-cont"><nav aria-label="Main" class="lt-es-pills lt-es-center"><router-link v-for="n in links" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link></nav></div></div>
      </header>
    </template>

    <header v-else-if="e.shell === 'tabs'" class="lt-es-tabs">
      <div class="lt-cont lt-es-row"><LtBrand mark :size="20" /><span class="lt-es-trail"><LtAccount short /><LtThemeToggle /><LtButton :to="cta.to">{{ cta.label }}</LtButton></span></div>
      <div class="lt-es-tabrow"><div class="lt-cont"><nav aria-label="Main" class="lt-es-tablist"><router-link v-for="n in links" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link></nav></div></div>
    </header>

    <header v-else-if="e.shell === 'dock'" class="lt-es-top">
      <div class="lt-cont lt-es-row"><LtBrand mark :size="20" /><span class="lt-es-trail"><LtAccount short /><LtThemeToggle /><LtButton :to="cta.to">{{ cta.label }}</LtButton></span></div>
    </header>

    <header v-else class="lt-es-top lt-es-bar">
      <div class="lt-cont lt-es-row">
        <LtBrand mark :size="20" />
        <nav aria-label="Main" class="lt-es-pills"><router-link v-for="n in links" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link></nav>
        <span class="lt-es-trail"><LtAccount short /><LtThemeToggle /><LtButton :to="cta.to">{{ cta.label }}</LtButton></span>
      </div>
    </header>

    <div v-if="e.shell === 'side' || e.shell === 'right'" class="lt-es-main"><slot /><ThemeFooter /></div>
    <template v-else>
      <slot />
      <ThemeFooter />
    </template>

    <nav v-if="e.shell === 'dock'" aria-label="Main" class="lt-es-dock">
      <router-link v-for="n in links" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined">{{ n.label }}</router-link>
    </nav>
  </div>
</template>
