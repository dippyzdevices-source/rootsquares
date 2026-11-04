<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Wordmark from '@rootsquares/ui/components/Wordmark.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AccountMenu from '@/components/ui/AccountMenu.vue'
import PrefControls from '@rootsquares/ui/components/PrefControls.vue'

// The one header of the public site, the platform pages and the owner console (moved here unchanged from PlatformLayout so every page shows the same
// bar). Mirrors Landing's top bar in design/rootsquares-platform-brass/screens/A.jsx (.bs-top, .bs-nav). Nav (design v4): Features, Pricing, Case studies, Contact, then
// Owner console (platform admins), Dashboard and Sign out, or Sign in and Start free; below 760px a menu button replaces them.
const { t } = useI18n()
const route = useRoute()
const open = ref(false)
watch(() => route.fullPath, () => { open.value = false })

const links = [
  { to: '/#features', key: 'nav.features', match: (p: string) => p === '/' },
  { to: '/pricing', key: 'nav.pricing', match: (p: string) => p === '/pricing' },
  { to: '/case-study/bca', key: 'nav.caseStudies', match: (p: string) => p.startsWith('/case-study') },
  { to: '/contact', key: 'nav.contact', match: (p: string) => p === '/contact' },
]
</script>

<template>
  <header class="bs-top bs-top--site">
    <RouterLink to="/" style="text-decoration: none"><Wordmark :size="24" /></RouterLink>
    <nav class="bs-nav bs-nav--site" :aria-label="t('nav.main')">
      <RouterLink v-for="l in links" :key="l.to" :to="l.to" :aria-current="l.match(route.path) && l.to !== '/#features' ? 'page' : undefined">{{ t(l.key) }}</RouterLink>
    </nav>
    <span class="bs-sp" />
    <div class="bs-end pt-ctl"><PrefControls /><AccountMenu /></div>
    <AppButton class="bs-burger" variant="ghost" icon-only :icon="open ? 'x' : 'menu'" :label="open ? t('common.closeMenu') : t('common.openMenu')" :aria-expanded="open" aria-controls="mk-menu" @click="open = !open" />
  </header>
  <nav v-if="open" id="mk-menu" class="mk-menu bs-menu" :aria-label="t('nav.main')">
    <RouterLink v-for="l in links" :key="l.to" :to="l.to" :aria-current="l.match(route.path) && l.to !== '/#features' ? 'page' : undefined">{{ t(l.key) }}</RouterLink>
    <div class="mk-menu__pref"><AccountMenu inline /></div>
    <div class="mk-menu__pref"><PrefControls /></div>
  </nav>
</template>
