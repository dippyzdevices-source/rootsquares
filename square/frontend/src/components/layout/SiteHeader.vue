<script setup lang="ts">
import { moduleEnabled, type ModuleKey } from '../../services/modules'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AccountMenu, { type AccountMenuItem } from '../ui/AccountMenu.vue'
import BaseAvatar from '../ui/BaseAvatar.vue'
import BaseButton from '../ui/BaseButton.vue'
import NavIcon from '../ui/NavIcon.vue'
import SiteName from '../ui/SiteName.vue'
import SquareMark from '../ui/SquareMark.vue'
import ThemeToggle from '../ui/ThemeToggle.vue'
import { EMPTY_HOME_CONTENT, loadHomeContent, logoHeight, menuName, type PageKey } from '../../services/siteContent'
import { useAuthStore } from '../../stores/auth'
import { useLookup } from '../../composables/useLookup'

// Shared with every real area of the site (public pages, member portal, admin console,
// check-in) — mirrors the design system's own composition (see ui_kits/website/index.html),
// where the same UtilityBar/SiteHeader wraps every screen and each area's own content
// (a sidebar AppShell for Portal/Admin) renders underneath it, not instead of it.
const { label: userRoleLabel } = useLookup('user_role')
const mobileNavOpen = ref(false)
const home = ref({ ...EMPTY_HOME_CONTENT }) // the square's own top-bar text and tagline (W6-R64)
onMounted(() => {
  void loadHomeContent().then((content) => (home.value = content))
})
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

// A module the owner turned off has no link (W8-R9); Heritage (About) and Contact are core.
// `label` is a getter: the page's name as the square set it (W11-R43), else the default.
const navLink = (page: PageKey, label: string, to: string, module?: ModuleKey) => ({
  to,
  module,
  get label() {
    return menuName(page, label)
  },
})
const navItems = [
  navLink('events', 'Events', '/events', 'events'),
  navLink('heritage', 'About', '/about', 'about'),
  navLink('gallery', 'Gallery', '/gallery', 'gallery'),
  navLink('membership', 'Membership', '/membership', 'memberships'),
  navLink('news', 'News', '/news', 'news'),
  navLink('contact', 'Contact', '/contact', 'contact'),
  { to: '/donate', module: 'donations' as ModuleKey, label: 'Donate' },
  // The sign-up band lives under the news list; a square with the newsletter but no news gets its own page (W14-R13)
  ...(moduleEnabled('news') ? [] : [{ to: '/newsletter', module: 'newsletter' as ModuleKey, label: 'Newsletter' }]),
].filter((item) => moduleEnabled(item.module))

const checkinOn = moduleEnabled('checkin') // W8-R22
const membershipsOn = moduleEnabled('memberships')
const accountName = computed(() => auth.displayName ?? 'My Account')
const accountShortName = computed(() => (auth.displayName ? auth.displayName.split(' ')[0] : 'My Account'))
const accountMeta = computed(() => (auth.user ? userRoleLabel(auth.user.role) : null))

const accountItems = computed<AccountMenuItem[]>(() => {
  const portal: (AccountMenuItem & { module?: ModuleKey })[] = [
    { id: 'dashboard', label: 'My portal', to: '/member', icon: 'dashboard' },
    { id: 'tickets', label: 'My tickets', to: '/member/tickets', icon: 'ticket', module: 'tickets' as const },
    { id: 'family', label: 'Family', to: '/member/family', icon: 'users', module: 'memberships' as const },
    { id: 'payments', label: 'Payments', to: '/member/payments', icon: 'receipt', module: 'payments' as const },
    { id: 'settings', label: 'Settings', to: '/member/settings', icon: 'settings' },
  ]
  const items: AccountMenuItem[] = portal.filter((item) => moduleEnabled(item.module))
  if (auth.isAdmin || auth.isVolunteer) {
    items.push({ id: 'chrome-divider', label: '', divider: true })
  }
  if (auth.isAdmin) {
    items.push({ id: 'admin', label: 'Admin console', to: '/admin', icon: 'shield' })
  }
  if (auth.isAdmin || auth.isVolunteer) {
    if (moduleEnabled('checkin')) items.push({ id: 'checkin', label: 'Check-in', to: '/checkin', icon: 'scan' })
  }
  items.push({ id: 'signout-divider', label: '', divider: true })
  items.push({ id: 'signout', label: 'Sign out', icon: 'log-out', tone: 'danger' })
  return items
})

async function handleLogout() {
  await auth.signOut()
  router.push('/')
}

function handleAccountSelect(id: string) {
  if (id === 'signout') handleLogout()
}
</script>

<template>
  <div class="ds-utility-bar">
    <div class="ds-container ds-utility-bar-inner">
      <span class="ds-utility-locale">{{ home.utility_text }}</span>
      <div class="ds-utility-links">
        <router-link v-if="moduleEnabled('contact')" to="/contact" class="ds-utility-link" :class="{ 'ds-utility-link-active': route.path === '/contact' }">
          Contact
        </router-link>
        <router-link
          v-if="moduleEnabled(auth.isAuthenticated ? 'account' : 'login')"
          :to="auth.isAuthenticated ? '/member' : '/login'"
          class="ds-utility-link"
          :class="{ 'ds-utility-link-active': route.path.startsWith('/member') || route.path === '/login' }"
        >
          {{ auth.isAuthenticated ? 'My portal' : 'Sign in' }}
        </router-link>
        <ThemeToggle />
      </div>
    </div>
  </div>

  <header class="ds-navbar">
    <div class="ds-container ds-navbar-inner">
      <router-link to="/" class="ds-wordmark-link">
        <SquareMark :size="logoHeight(home.logo_size)" style="margin-right: 8px" />
        <span class="ds-wordmark-stack">
          <SiteName :variant="home.name_style" />
          <span v-if="home.tagline_local" class="ds-wordmark-bn ds-bn">{{ home.tagline_local }}</span>
        </span>
      </router-link>

      <nav class="ds-navbar-links">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="ds-navlink"
          exact-active-class="router-link-exact-active"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <div class="ds-navbar-actions">
        <div class="ds-navbar-trailing">
          <template v-if="!auth.isAuthenticated">
            <BaseButton to="/login" variant="ghost" size="sm">Login</BaseButton>
            <BaseButton v-if="membershipsOn" to="/membership" variant="primary" size="sm">Become a member</BaseButton>
          </template>
          <AccountMenu
            v-else
            :name="accountName"
            :short-name="accountShortName"
            :email="auth.user?.email ?? null"
            :avatar-url="auth.avatarUrl"
            :meta="accountMeta"
            :items="accountItems"
            @select="handleAccountSelect"
          />
        </div>
        <button
          class="ds-navbar-burger"
          aria-label="Toggle navigation"
          @click="mobileNavOpen = !mobileNavOpen"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      </div>

      <nav v-if="mobileNavOpen" class="ds-navbar-mobile">
        <template v-if="auth.isAuthenticated">
          <router-link
            to="/member"
            class="flex items-center justify-end gap-2 py-2 self-end no-underline"
            @click="mobileNavOpen = false"
          >
            <span class="ds-navlink" style="padding: 0; border-bottom: none">{{ accountName }}</span>
            <BaseAvatar :src="auth.avatarUrl" :name="auth.displayName" size="sm" />
          </router-link>
          <span class="ds-account-menu-divider" />
        </template>

        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="ds-navlink"
          exact-active-class="router-link-exact-active"
          @click="mobileNavOpen = false"
        >
          {{ item.label }}
        </router-link>

        <template v-if="!auth.isAuthenticated">
          <div style="display: flex; flex-direction: column; gap: var(--ds-space-2); margin-top: var(--ds-space-3)">
            <BaseButton to="/login" variant="ghost" full-width @click="mobileNavOpen = false">Login</BaseButton>
            <BaseButton v-if="membershipsOn" to="/membership" variant="primary" full-width @click="mobileNavOpen = false">Become a member</BaseButton>
          </div>
        </template>
        <template v-else>
          <span class="ds-account-menu-divider" />
          <router-link
            v-if="auth.isAdmin"
            to="/admin"
            class="ds-navlink"
            @click="mobileNavOpen = false"
          >
            Admin
          </router-link>
          <router-link
            v-if="checkinOn && (auth.isAdmin || auth.isVolunteer)"
            to="/checkin"
            class="ds-navlink"
            @click="mobileNavOpen = false"
          >
            Check-in
          </router-link>
          <button
            type="button"
            class="ds-navlink ds-mobile-logout"
            @click="
              handleLogout();
              mobileNavOpen = false
            "
          >
            <NavIcon name="log-out" class="ds-account-menu-row-icon" />
            Logout
          </button>
        </template>
      </nav>
    </div>
  </header>
</template>
