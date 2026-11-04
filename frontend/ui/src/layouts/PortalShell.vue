<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppIcon from '../components/AppIcon.vue'
import AppButton from '../components/AppButton.vue'
import Wordmark from '../components/Wordmark.vue'
import PrefControls from '../components/PrefControls.vue'
import { useUiStore } from '../stores/ui'

// Shell of the platform portal (square owner) and of the admin console (design v4 screens/I.jsx Console, export/screens.md "Platform portal shell"). It knows no
// store and no API: the layout around it gives the person's name, the account link and what to do on Sign out (the customer app and the admin application differ).
// No marketing nav in here. Desktop: console header 64px, 56px on a phone (wordmark 24, as on the home page; W23-R53; area label, mode switch, avatar), 208px side bar. Mobile: header 48px, a 64px
// bottom bar with the first four items and More, and a 300px drawer with every item (44px rows).
export interface NavItem { to: string; label: string; icon: string; exact?: boolean; group?: string; count?: number } // `group`: a small label above the first item of a group (the admin console); `count`: a number shown at the end of the row when above 0 (what waits, W25-R33)
const props = defineProps<{ nav: NavItem[]; area: string; eyebrow?: string; navLabel: string; userName?: string; userEmail?: string; userSub?: string; accountTo?: string; tone?: 'admin' }>()
const emit = defineEmits<{ signOut: [] }>()
const { t } = useI18n()
const route = useRoute()
const open = ref(false)
const menu = ref(false) // the account menu under the avatar: who is signed in, Your account, the theme, Sign out
const ui = useUiStore()
watch(() => route.fullPath, () => { open.value = false; menu.value = false })

const current = (n: NavItem) => (n.exact ? route.path === n.to : route.path === n.to || route.path.startsWith(n.to + '/'))
const initials = computed(() => (props.userName || '?').split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join(''))
// bottom bar: with 5 items or fewer all of them, otherwise the first four and More
const bottom = computed(() => (props.nav.length <= 5 ? props.nav : props.nav.slice(0, 4)))
</script>

<template>
  <div class="rs-appwrap">
    <div class="pt" :class="{ 'pt--admin': tone === 'admin' }">
      <a href="#main" class="rs-sr">{{ t('app.skipToContent') }}</a>
      <header class="bs-top pt-top">
        <AppButton class="pt-burger" variant="ghost" icon-only icon="menu" :label="t('common.openMenu')" :aria-expanded="open" aria-controls="pt-drawer" style="min-width: 44px; min-height: 44px" @click="open = true" />
        <RouterLink to="/" style="text-decoration: none" :aria-label="t('app.name')"><Wordmark :size="24" /></RouterLink>
        <span class="pt-pill" :class="{ 'pt-pill--quiet': tone !== 'admin' }">{{ area }}</span>
        <span class="bs-sp" />
        <div class="pt-ctl" @keydown.esc="menu = false">
          <PrefControls />
          <i class="pt-sep" aria-hidden="true" />
          <AppButton class="pt-so" variant="ghost" size="sm" icon="out" :label="t('plat.nav.signOut')" @click="emit('signOut')"><span class="pt-so-t">{{ t('plat.nav.signOut') }}</span></AppButton>
          <template v-if="accountTo">
            <i class="pt-sep" aria-hidden="true" />
            <div class="pt-mw">
              <button type="button" class="pt-av" aria-haspopup="menu" :aria-expanded="menu" :aria-label="t('plat.account.menu')" @click.stop="menu = !menu">{{ initials }}<i class="pt-av__dot" aria-hidden="true" /></button>
              <template v-if="menu">
                <div class="pt-menu-bg" @click="menu = false" />
                <div class="pt-menu" role="menu">
                  <div class="pt-who"><span class="pt-av pt-av--static">{{ initials }}</span><div><b>{{ userName }}</b><small v-if="userEmail && userEmail !== userName">{{ userEmail }}</small><small v-if="userSub">{{ userSub }}</small></div></div>
                  <RouterLink :to="accountTo" role="menuitem" class="pt-mi" @click="menu = false"><AppIcon name="users" :size="18" />{{ t('plat.account.link') }}</RouterLink>
                  <button type="button" role="menuitem" class="pt-mi" @click="ui.toggleMode(); menu = false"><AppIcon :name="ui.mode === 'dark' ? 'sun' : 'moon'" :size="18" />{{ ui.mode === 'dark' ? t('common.lightMode') : t('common.darkMode') }}</button>
                  <button type="button" role="menuitem" class="pt-mi pt-mi--danger" @click="menu = false; emit('signOut')"><AppIcon name="out" :size="18" />{{ t('plat.nav.signOut') }}</button>
                </div>
              </template>
            </div>
          </template>
        </div>
      </header>
      <div class="pt-body">
        <aside class="pt-side">
          <span v-if="eyebrow" class="rs-eyebrow">{{ eyebrow }}</span>
          <nav class="pt-nav" :aria-label="navLabel">
            <template v-for="(n, i) in nav" :key="n.to"><span v-if="n.group && n.group !== nav[i - 1]?.group" class="pt-gl">{{ n.group }}</span><RouterLink :to="n.to" :aria-current="current(n) ? 'page' : undefined"><AppIcon :name="n.icon" :size="16" />{{ n.label }}<span v-if="n.count" class="rs-badge pt-count">{{ n.count }}</span></RouterLink></template>
          </nav>
        </aside>
        <main id="main" class="pt-main"><slot /></main>
      </div>
      <nav class="pt-bnav" :aria-label="navLabel">
        <RouterLink v-for="n in bottom" :key="n.to" :to="n.to" :aria-current="current(n) ? 'page' : undefined"><AppIcon :name="n.icon" :size="18" />{{ n.label }}</RouterLink>
        <button v-if="nav.length > 5" type="button" aria-haspopup="dialog" @click="open = true"><AppIcon name="more" :size="18" />{{ t('portal.more') }}</button>
      </nav>
      <template v-if="open">
        <div class="pt-scrim" @click="open = false" />
        <aside id="pt-drawer" class="pt-drawer" role="dialog" :aria-label="t('portal.menu')" @keydown.esc="open = false">
          <div class="bs-row" style="justify-content: space-between"><Wordmark :size="24" /><AppButton variant="ghost" icon-only icon="x" :label="t('common.closeMenu')" style="min-width: 44px; min-height: 44px" @click="open = false" /></div>
          <span v-if="eyebrow" class="rs-eyebrow">{{ eyebrow }}</span>
          <nav class="pt-nav" :aria-label="navLabel">
            <template v-for="(n, i) in nav" :key="n.to"><span v-if="n.group && n.group !== nav[i - 1]?.group" class="pt-gl">{{ n.group }}</span><RouterLink :to="n.to" :aria-current="current(n) ? 'page' : undefined"><AppIcon :name="n.icon" :size="16" />{{ n.label }}<span v-if="n.count" class="rs-badge pt-count">{{ n.count }}</span></RouterLink></template>
          </nav>
        </aside>
      </template>
    </div>
  </div>
</template>
