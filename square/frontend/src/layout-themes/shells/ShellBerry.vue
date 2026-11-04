<script setup lang="ts">
import { computed } from 'vue'
import ThemeFooter from '../ThemeFooter.vue'
import LtThemeToggle from '../parts/LtThemeToggle.vue'
import LtAccount from '../parts/LtAccount.vue'
import LtButton from '../parts/LtButton.vue'
import { cta, dayMonth, eventsOn, navItems } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import { useActive } from '../useShellBits'
import { squareProfile } from '../../services/squareConfig'

// Berry Courtyard: a fixed panel on the left with the name, the pages and the next event; the page scrolls beside it (W9-R5).
const { isActive } = useActive()
const { home, nextEvent } = useSiteData()
const when = computed(() => (nextEvent.value ? dayMonth(nextEvent.value.start_datetime) : null))
</script>

<template>
  <div class="lt-shell lt-berry-shell">
    <aside class="lt-bp">
      <div class="lt-bp-in">
        <router-link to="/" class="lt-bp-name">{{ squareProfile.name }}</router-link>
        <span v-if="home.tagline_local" class="lt-bp-local ds-bn">{{ home.tagline_local }}</span>
        <nav aria-label="Main" class="lt-bp-nav">
          <router-link v-for="(n, i) in navItems" :key="n.key" :to="n.to" :class="{ 'is-active': isActive(n.to) }" :aria-current="isActive(n.to) ? 'page' : undefined"><i class="lt-mono">{{ String(i + 1).padStart(2, '0') }}</i>{{ n.label }}</router-link>
        </nav>
        <div class="lt-bp-foot">
          <router-link v-if="eventsOn && nextEvent && when" :to="`/events/${nextEvent.slug}`" class="lt-bp-next">
            <small>UP NEXT</small>
            <strong>{{ nextEvent.title }}</strong>
            <span>{{ when.day }} {{ when.month }}<template v-if="nextEvent.venue"> · {{ nextEvent.venue }}</template></span>
          </router-link>
          <LtButton :to="cta.to" kind="w">{{ cta.label }}</LtButton>
          <span class="lt-bp-acc"><LtAccount class="lt-bp-account" /><LtThemeToggle /></span>
        </div>
      </div>
    </aside>
    <div class="lt-bp-main">
      <slot />
      <ThemeFooter />
    </div>
  </div>
</template>
