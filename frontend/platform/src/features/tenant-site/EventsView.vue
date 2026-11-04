<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTenantStore } from '@/stores/tenant'
import { useSite } from './useSite'
import TEventList from './components/TEventList.vue'

const { t } = useI18n()
const tenant = useTenantStore()
const { themeId } = useSite()
const live = computed(() => tenant.events.filter((e) => e.status === 'live'))
</script>

<template>
  <section class="t-sec">
    <div class="t-wrap">
      <h1 style="font-size: clamp(32px, 5vw, 48px)">{{ t('site.eventsTitle') }}</h1>
      <p class="t-muted" style="margin: 8px 0 24px">{{ t('site.eventsText') }}</p>
      <TEventList :events="live" :theme-id="themeId" />
    </div>
  </section>
</template>
