<script setup lang="ts">
import { computed } from 'vue'
import SocialIcon from '../components/ui/SocialIcon.vue'
import LtThemeToggle from './parts/LtThemeToggle.vue'
import { moduleEnabled } from '../services/modules'
import { squareProfile } from '../services/squareConfig'
import LtAccount from './parts/LtAccount.vue'
import LtBrand from './parts/LtBrand.vue'
import { activeLayout } from './layouts'
import { navItems } from './useSiteLayout'
import { useSiteData } from './useSiteData'

// The footer in the theme's arrangement (W9-R5): cols = brand, links and contact in columns; line = one row; big = links and a giant name.
// The words are the square's own (Settings, Content); nothing set = not shown.
const layout = activeLayout!
const { home, email, phone, address } = useSiteData()
const links = computed(() => navItems.filter((n) => n.key !== 'home'))
const copyright = computed(() => home.value.footer_copyright || `© ${new Date().getFullYear()} ${squareProfile.name}`)
const blurb = computed(() => home.value.footer_blurb || '')
</script>

<template>
  <footer class="lt-footer" :class="`lt-footer-${layout.ft}`" :style="layout.fr ? { borderRadius: layout.fr } : undefined">
    <div class="lt-cont">
      <template v-if="layout.ft === 'cols' || layout.ft === 'band'">
        <div class="lt-fcols">
          <div>
            <LtBrand mark :size="26" />
            <p v-if="blurb" class="lt-footer-blurb">{{ blurb }}</p>
            <p v-if="home.footer_registration" class="lt-footer-blurb">{{ home.footer_registration }}</p>
          </div>
          <nav aria-label="Footer">
            <h2 class="lt-footer-h">Explore</h2>
            <router-link v-for="n in links" :key="n.key" :to="n.to">{{ n.label }}</router-link>
            <router-link v-if="moduleEnabled('committee')" to="/committee">Committee</router-link>
            <router-link v-if="moduleEnabled('tickets')" to="/orders/lookup">Find your order</router-link>
          </nav>
          <div>
            <h2 class="lt-footer-h">Contact</h2>
            <a v-if="email" :href="`mailto:${email}`">{{ email }}</a>
            <a v-if="phone" :href="`tel:${phone.replace(/\s+/g, '')}`">{{ phone }}</a>
            <span v-if="address">{{ address }}</span>
            <router-link v-if="!email && !phone && !address && moduleEnabled('contact')" to="/contact">Contact page</router-link>
          </div>
        </div>
      </template>
      <template v-else-if="layout.ft === 'big'">
        <div class="lt-footer-row">
          <nav aria-label="Footer" class="lt-footer-links">
            <router-link v-for="n in links" :key="n.key" :to="n.to">{{ n.label }}</router-link>
            <router-link v-if="moduleEnabled('committee')" to="/committee">Committee</router-link>
            <router-link v-if="moduleEnabled('tickets')" to="/orders/lookup">Find your order</router-link>
          </nav>
          <a v-if="email" :href="`mailto:${email}`" class="lt-footer-mail">{{ email }}</a>
        </div>
      </template>
      <template v-else>
        <div class="lt-footer-row">
          <LtBrand v-if="layout.shell !== 'still'" :size="20" />
          <nav aria-label="Footer" class="lt-footer-links">
            <router-link v-for="n in links" :key="n.key" :to="n.to">{{ n.label }}</router-link>
            <router-link v-if="moduleEnabled('committee')" to="/committee">Committee</router-link>
            <router-link v-if="moduleEnabled('tickets')" to="/orders/lookup">Find your order</router-link>
          </nav>
          <a v-if="email" :href="`mailto:${email}`" class="lt-footer-mail">{{ email }}</a>
        </div>
      </template>
      <ul v-if="home.social_links.length" class="lt-footer-social">
        <li v-for="link in home.social_links" :key="link.network">
          <a :href="link.url" target="_blank" rel="noopener noreferrer" :aria-label="`${squareProfile.name} on ${link.network}`"><SocialIcon :network="link.network" /></a>
        </li>
      </ul>
      <div class="lt-footer-base">
        <span>{{ copyright }}</span>
        <span class="lt-footer-legal">
          <router-link v-if="moduleEnabled('legal')" to="/privacy">Privacy Policy</router-link>
          <router-link v-if="moduleEnabled('legal')" to="/terms-of-sale">Terms of Sale</router-link>
          <LtAccount :menu="false" />
          <LtThemeToggle />
        </span>
      </div>
    </div>
    <div v-if="layout.ft === 'big'" class="lt-footer-giant" aria-hidden="true">{{ squareProfile.name }}</div>
  </footer>
</template>
