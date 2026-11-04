<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useThemeLayout } from '@/components/ui/themeScope'
import { useTenantStore } from '@/stores/tenant'
import TPlaceholder from './components/TPlaceholder.vue'

const { t } = useI18n()
const tenant = useTenantStore()
const layout = useThemeLayout()
</script>

<template>
  <section class="t-sec">
    <div class="t-wrap">
      <h1 style="font-size: clamp(32px, 5vw, 48px)">{{ t('site.committeeTitle') }}</h1>
      <p class="t-muted" style="margin: 8px 0 24px">{{ t('site.committeeText') }}</p>
      <div class="t-people">
        <article v-for="c in tenant.committee.filter((m) => m.visible)" :key="c.id" class="t-card t-person">
          <TPlaceholder :ratio="layout.img === 'arch' ? '4/5' : '1/1'" label="portrait" />
          <div><b>{{ c.name }}</b><i>{{ c.role }}</i><small>{{ c.email }}</small></div>
        </article>
      </div>
    </div>
  </section>
</template>
