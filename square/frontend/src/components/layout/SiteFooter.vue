<script setup lang="ts">
import { onMounted, ref } from 'vue'
import SiteName from '../ui/SiteName.vue'
import SocialIcon from '../ui/SocialIcon.vue'
import SquareMark from '../ui/SquareMark.vue'
import { moduleEnabled } from '../../services/modules'
import { squareProfile } from '../../services/squareConfig'
import { fetchSettings } from '../../services/settingsApi'
import { EMPTY_HOME_CONTENT, loadHomeContent, logoHeight, menuName } from '../../services/siteContent'

// rootsquares W6-R36: the footer shows the square's own name and the contact email its admin set in /admin/settings. bca-oslo's organisation
// number, tagline and Facebook link were BCA's own and are gone (a square can get such fields later).
const contactEmail = ref('')
const home = ref({ ...EMPTY_HOME_CONTENT }) // the square's own tagline (W6-R64)
onMounted(async () => {
  void loadHomeContent().then((content) => (home.value = content))
  try {
    contactEmail.value = (await fetchSettings()).contact_email
  } catch {
    contactEmail.value = '' // the footer stays usable without it
  }
})
</script>

<template>
  <footer class="ds-footer">
    <div class="ds-container ds-footer-grid">
      <div class="ds-footer-brand" style="gap: var(--ds-space-2)">
        <router-link to="/" class="ds-wordmark-link">
          <SquareMark :size="logoHeight(home.logo_size)" on-dark style="margin-right: 8px" />
          <span class="ds-wordmark-stack">
            <SiteName :variant="home.name_style" on-dark />
            <span v-if="home.tagline_local" class="ds-wordmark-bn ds-wordmark-bn-onDark ds-bn">{{ home.tagline_local }}</span>
          </span>
        </router-link>
        <p v-if="home.footer_registration" class="ds-footer-blurb" style="max-width: 48ch">{{ home.footer_registration }}</p>
        <p v-if="home.footer_blurb" class="ds-footer-blurb" style="max-width: 48ch">{{ home.footer_blurb }}</p>
        <div v-if="home.social_links.length" style="margin-top: var(--ds-space-2)">
          <p class="ds-eyebrow" style="color: var(--ds-saffron-300); margin-bottom: var(--ds-space-1)">Follow us</p>
          <ul class="ds-footer-list ds-footer-social" style="gap: var(--ds-space-3); flex-direction: row">
            <li v-for="link in home.social_links" :key="link.network">
              <a :href="link.url" class="footer-social" :class="`footer-social-${link.network}`" target="_blank" rel="noopener noreferrer" :aria-label="`${squareProfile.name} on ${link.network}`">
                <SocialIcon :network="link.network" />
              </a>
            </li>
          </ul>
        </div>
      </div>

      <div style="display: flex; flex-direction: column; gap: var(--ds-space-3); align-items: flex-end; text-align: right">
        <div v-if="moduleEnabled('committee')">
          <p class="ds-eyebrow" style="color: var(--ds-saffron-300); margin-bottom: var(--ds-space-1)">Organisation</p>
          <ul class="ds-footer-list" style="gap: var(--ds-space-1)">
            <li><router-link to="/committee">{{ menuName('committee', 'Committee') }}</router-link></li>
          </ul>
        </div>

        <div>
          <p class="ds-eyebrow" style="color: var(--ds-saffron-300); margin-bottom: var(--ds-space-1)">Get in touch</p>
          <ul class="ds-footer-list" style="gap: var(--ds-space-1)">
            <li v-if="contactEmail"><a :href="`mailto:${contactEmail}`">{{ contactEmail }}</a></li>
            <li v-if="moduleEnabled('contact')"><router-link to="/contact">{{ menuName('contact', 'Contact page') }}</router-link></li>
            <li v-if="moduleEnabled('tickets')"><router-link to="/orders/lookup">Find your order</router-link></li>
          </ul>
        </div>
      </div>
    </div>

    <div class="ds-container">
      <div class="ds-motif ds-motif-onDark" style="color: var(--ds-saffron-300); max-width: none; margin: var(--ds-space-6) 0 var(--ds-space-4)">
        <span></span><span class="ds-motif-glyph">❖</span><span></span>
      </div>
    </div>

    <div class="ds-container ds-footer-bottom">
      <p>{{ home.footer_copyright || `© ${new Date().getFullYear()} ${squareProfile.name}` }}</p>
      <span style="display: inline-flex; gap: var(--ds-space-4); flex-wrap: wrap">
        <router-link v-if="moduleEnabled('legal')" to="/privacy">Privacy Policy</router-link>
        <router-link v-if="moduleEnabled('legal')" to="/terms-of-sale">Terms of Sale</router-link>
      </span>
    </div>
  </footer>
</template>

<style scoped>
.footer-social-fb:hover,
.footer-social-fb:active,
.footer-social-fb:focus-visible {
  color: #1877f2;
}
</style>
