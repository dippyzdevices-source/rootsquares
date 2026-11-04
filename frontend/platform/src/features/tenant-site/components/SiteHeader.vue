<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useThemeLayout } from '@/components/ui/themeScope'
import { useTenantStore } from '@/stores/tenant'
import TButton from './TButton.vue'

// Header in the theme's layout: left, center, bar (two rows) or side. Below 900px every layout uses the compact bar with a menu button.
const props = defineProps<{ themeId: string }>()
const { t } = useI18n()
const route = useRoute()
const tenant = useTenantStore()
const layout = useThemeLayout()
const open = ref(false)
watch(() => route.fullPath, () => { open.value = false })

const items = [
  { path: '', key: 'home' }, { path: '/events', key: 'events' }, { path: '/membership', key: 'membership' },
  { path: '/committee', key: 'committee' }, { path: '/gallery', key: 'gallery' }, { path: '/news', key: 'articles' }, { path: '/contact', key: 'contact' },
]
const to = (p: string) => `/site/${props.themeId}${p}`
const current = (p: string) => (route.path === to(p) || (p === '/events' && route.path.startsWith(to('/events/'))) ? 'page' : undefined)
const initials = () => tenant.name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
</script>

<template>
  <div v-if="layout.header === 'two-row'" class="t-bar"><div class="t-wrap">EN / NO</div></div>
  <header class="t-head">
    <div class="t-wrap t-head__in">
      <RouterLink :to="to('')" class="t-logo" :aria-label="tenant.name"><span class="t-logo__mark" aria-hidden="true">{{ initials() }}</span><span class="t-logo__name">{{ tenant.name }}</span></RouterLink>
      <nav class="t-nav" :aria-label="t('nav.siteNav')">
        <RouterLink v-for="i in items" :key="i.key" :to="to(i.path)" :aria-current="current(i.path)">{{ t(`site.${i.key}`) }}</RouterLink>
      </nav>
      <TButton class="t-head__cta" :to="to('/membership')">{{ t('site.joinCta') }}</TButton>
      <button type="button" class="t-menu-btn" :aria-expanded="open" aria-controls="t-drawer" @click="open = !open">{{ open ? t('common.close') : t('nav.menu') }}</button>
    </div>
    <nav v-if="open" id="t-drawer" class="t-drawer" :aria-label="t('nav.siteNav')">
      <RouterLink v-for="i in items" :key="i.key" :to="to(i.path)" :aria-current="current(i.path)">{{ t(`site.${i.key}`) }}</RouterLink>
    </nav>
  </header>
  <nav v-if="layout.header === 'two-row'" class="t-subnav" :aria-label="t('nav.siteNav')">
    <div class="t-wrap"><RouterLink v-for="i in items" :key="i.key" :to="to(i.path)" :aria-current="current(i.path)">{{ t(`site.${i.key}`) }}</RouterLink></div>
  </nav>
</template>
