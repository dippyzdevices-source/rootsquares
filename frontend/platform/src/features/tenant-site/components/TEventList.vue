<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useThemeLayout } from '@/components/ui/themeScope'
import type { BcaEvent } from '@/mock/bca'
import TButton from './TButton.vue'
import TPlaceholder from './TPlaceholder.vue'

// Events as cards (grid) or a dated list, following the theme's layout flag.
const props = defineProps<{ events: BcaEvent[]; themeId: string }>()
const { t } = useI18n()
const layout = useThemeLayout()
const from = (e: BcaEvent) => Math.min(...e.tickets.map((x) => x.price))
const price = (e: BcaEvent) => (from(e) === 0 ? t('site.free') : `NOK ${from(e)}`)
const link = (e: BcaEvent) => `/site/${props.themeId}/events/${e.id}`
</script>

<template>
  <div v-if="layout.events === 'grid'" class="t-events-grid">
    <article v-for="e in events" :key="e.id" class="t-event">
      <TPlaceholder ratio="16/10" shape="none" label="photo" />
      <div class="t-event__body">
        <div><span class="t-badge">{{ e.tag }}</span></div>
        <h3><RouterLink :to="link(e)">{{ e.title }}</RouterLink></h3>
        <div class="t-event__meta">{{ e.dateLabel }}<br>{{ e.place }}</div>
        <div class="t-event__foot"><strong style="color: var(--t-text-strong)">{{ price(e) }}</strong><TButton variant="outline" :to="link(e)">{{ t('site.details') }}</TButton></div>
      </div>
    </article>
  </div>
  <div v-else class="t-events-list">
    <article v-for="e in events" :key="e.id" class="t-levent">
      <div class="t-levent__date"><div class="t-levent__day">{{ e.day }}</div><div class="t-levent__mon">{{ e.month }}</div></div>
      <div class="t-levent__main"><h3><RouterLink :to="link(e)">{{ e.title }}</RouterLink></h3><div class="t-event__meta">{{ e.dateLabel }} · {{ e.place }}</div></div>
      <div class="t-row"><strong style="color: var(--t-text-strong)">{{ price(e) }}</strong><TButton variant="outline" :to="link(e)">{{ t('site.details') }}</TButton></div>
    </article>
  </div>
</template>
