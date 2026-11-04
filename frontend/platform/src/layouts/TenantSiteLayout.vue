<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import ThemeScope from '@/components/ui/ThemeScope.vue'
import PreviewChrome from '@/features/tenant-site/components/PreviewChrome.vue'
import { DEVICES, type Device } from '@/features/tenant-site/previewDevices'
import SiteHeader from '@/features/tenant-site/components/SiteHeader.vue'
import CookieNotice from '@/features/tenant-site/components/CookieNotice.vue'
import TButton from '@/features/tenant-site/components/TButton.vue'
import { useSite } from '@/features/tenant-site/useSite'
import { useTenantStore } from '@/stores/tenant'
import { getTheme } from '@rootsquares/ui/themes'
import '@/features/tenant-site/tenant.css'

// Tenant public site in the platform v3 Preview chrome (screens/G.jsx 6): the site sits in a framed viewport whose width follows the device switch;
// the tenant CSS answers to the frame width (container query "site"). The chrome is platform UI, outside the tenant scope.
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const tenant = useTenantStore()
const { themeId, to } = useSite()
const theme = computed(() => getTheme(themeId.value)!)
const accentStyle = computed(() => (tenant.accent ? { '--t-accent': tenant.accent, '--t-link': tenant.accent, '--t-btn-border': tenant.accent } : undefined))

const device = ref<Device>(typeof window !== 'undefined' && window.innerWidth <= 600 ? 'phone' : 'desktop')
function setTheme(id: string) {
  tenant.accent = ''
  router.replace({ name: route.name!, params: { ...route.params, themeId: id }, query: route.query })
}
</script>

<template>
  <div class="pv-page">
    <div class="bx-vp">
      <div :style="{ maxWidth: DEVICES[device].px + 'px' }">
        <div class="pv-site">
          <ThemeScope :theme="themeId" :mode="tenant.siteMode" :style="accentStyle">
            <div class="t-root" :data-header="theme.header" :data-flip="theme.flip">
              <a href="#t-main" class="rs-sr">{{ t('app.skipToContent') }}</a>
              <div class="t-shell">
                <SiteHeader :theme-id="themeId" />
                <div style="min-width: 0">
                  <main id="t-main">
                    <RouterView v-if="tenant.published" />
                    <section v-else class="t-center">
                      <div class="t-wrap t-center__in">
                        <div class="t-maint" aria-hidden="true">⏳</div>
                        <h1 style="font-size: clamp(28px, 4vw, 36px)">{{ t('site.maint.title') }}</h1>
                        <p style="margin: 0">{{ t('site.maint.text') }}</p>
                        <span class="t-note t-note--info" style="display: inline-block">{{ t('site.maint.back') }}</span>
                        <TButton variant="outline" @click="tenant.published = true">{{ t('site.publishAgain') }}</TButton>
                      </div>
                    </section>
                  </main>
                  <CookieNotice />
                  <footer class="t-foot">
                    <div class="t-wrap">
                      <div style="max-width: 36ch"><b>{{ tenant.name }}</b>{{ t('site.footerNote') }}</div>
                      <div>
                        <div>© 2026 {{ tenant.name }}</div>
                        <RouterLink to="/">{{ t('nav.backToPlatform') }}</RouterLink> ·
                        <RouterLink :to="to('/contact')">{{ t('site.contact') }}</RouterLink>
                      </div>
                    </div>
                  </footer>
                </div>
              </div>
            </div>
          </ThemeScope>
        </div>
      </div>
    </div>
    <PreviewChrome :theme-id="themeId" :mode="tenant.siteMode" :device="device" @update:theme-id="setTheme" @update:mode="(v) => (tenant.siteMode = v)" @update:device="(v) => (device = v)" />
  </div>
</template>
