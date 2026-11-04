<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTenantStore } from '@/stores/tenant'
import { useSite } from './useSite'
import TButton from './components/TButton.vue'
import THero from './components/THero.vue'
import TEventList from './components/TEventList.vue'

const { t } = useI18n()
const tenant = useTenantStore()
const { themeId, to } = useSite()
const live = computed(() => tenant.events.filter((e) => e.status === 'live'))
const stats = computed(() => [
  { value: String(tenant.members.length), label: t('site.stats.members') },
  { value: String(live.value.length), label: t('site.stats.events') },
  { value: String(tenant.committee.length), label: t('site.stats.committee') },
])
</script>

<template>
  <THero :eyebrow="t('site.seasonEyebrow')" :title="t('site.homeTitle')" :lead="t('site.homeLead')" :stats="stats">
    <TButton :to="to('/membership')">{{ t('site.joinCta') }}</TButton>
    <TButton variant="outline" :to="to('/events')">{{ t('site.viewEvents') }}</TButton>
  </THero>
  <section class="t-sec">
    <div class="t-wrap">
      <h2>{{ t('site.eventsTitle') }}</h2>
      <p class="t-muted" style="margin: 0 0 24px">{{ t('site.eventsText') }}</p>
      <TEventList :events="live.slice(0, 3)" :theme-id="themeId" />
    </div>
  </section>
</template>
