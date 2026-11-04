<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import DomainStatus from '@/components/ui/DomainStatus.vue'
import StatusChip from '@/components/ui/StatusChip.vue'
import { PREVIEW, type ModuleId } from '@/mock/landing'

// Mock preview of one module, built from the Brass list-row and KPI patterns (.bs-sec, .bs-r, .bs-kpis). Mock data only.
defineProps<{ id: ModuleId }>()
const { t } = useI18n()
const chip = (s: string) => s as 'live' | 'draft' | 'paid' | 'pending' | 'overdue'
</script>

<template>
  <section class="bs-sec" :aria-label="t(`landing.modules.${id}.name`)">
    <header>{{ t(`landing.preview.${id}`) }}</header>

    <template v-if="id === 'events'">
      <div v-for="e in PREVIEW.events" :key="e.title" class="bs-r">
        <span class="bs-date">{{ e.date }}</span>
        <div><div class="t">{{ e.title }}</div><div class="s">{{ e.meta }}</div></div>
        <StatusChip :status="chip(e.status)">{{ t(`common.status.${e.status}`) }}</StatusChip>
      </div>
    </template>

    <template v-else-if="id === 'tickets'">
      <div v-for="x in PREVIEW.tickets" :key="x.name" class="bs-r" style="grid-template-columns: 1fr auto auto">
        <div><div class="t">{{ x.name }}</div><div class="s">{{ x.qty }}</div></div>
        <span style="font-variant-numeric: tabular-nums">{{ x.price }}</span><span />
      </div>
      <div v-for="o in PREVIEW.orders" :key="o.ref" class="bs-r" style="grid-template-columns: 1fr auto auto">
        <div><div class="t">{{ o.who }}</div><div class="s">{{ o.ref }} · {{ o.total }}</div></div>
        <StatusChip :status="chip(o.status)">{{ t(`common.status.${o.status}`) }}</StatusChip>
        <span class="bs-mute" style="font-size: var(--text-xs)">{{ o.status === 'pending' ? t('landing.preview.markPaid') : '' }}</span>
      </div>
    </template>

    <template v-else-if="id === 'membership'">
      <div v-for="m in PREVIEW.members" :key="m.name" class="bs-r" style="grid-template-columns: 1fr auto">
        <div><div class="t">{{ m.name }}</div><div class="s">{{ m.kind }}</div></div>
        <StatusChip :status="chip(m.status)">{{ t(`common.status.${m.status}`) }}</StatusChip>
      </div>
    </template>

    <template v-else-if="id === 'committee'">
      <div v-for="c in PREVIEW.committee" :key="c.name" class="bs-r">
        <span class="rs-avatar" style="width: 32px; height: 32px; font-size: var(--text-xs)">{{ c.ini }}</span>
        <div><div class="t">{{ c.name }}</div><div class="s">{{ c.role }}</div></div><span />
      </div>
    </template>

    <template v-else-if="id === 'gallery'">
      <div class="bs-gal">
        <div v-for="g in PREVIEW.gallery" :key="g" class="bs-shot" style="min-height: 0; aspect-ratio: 1; font-size: 0.6rem; letter-spacing: 0.06em; padding: 4px">{{ g }}</div>
      </div>
      <div class="bs-r"><span class="bs-date">{{ PREVIEW.article.date }}</span><div><div class="t">{{ PREVIEW.article.title }}</div><div class="s">{{ PREVIEW.article.meta }}</div></div><AppIcon name="file" :size="14" /></div>
    </template>

    <template v-else-if="id === 'accounting'">
      <div class="bs-kpis" style="grid-template-columns: repeat(3, 1fr); border: 0; border-radius: 0; border-bottom: 1px solid var(--color-border)">
        <div class="bs-kpi"><span class="l">{{ t('landing.preview.income') }}</span><span class="v" style="font-size: var(--text-xl)">96 400</span></div>
        <div class="bs-kpi"><span class="l">{{ t('landing.preview.expenses') }}</span><span class="v" style="font-size: var(--text-xl)">61 150</span></div>
        <div class="bs-kpi"><span class="l">{{ t('landing.preview.balance') }}</span><span class="v" style="font-size: var(--text-xl)">35 250</span></div>
      </div>
      <div v-for="l in PREVIEW.ledger" :key="l.what" class="bs-r" style="grid-template-columns: 1fr auto">
        <div class="t" style="font-weight: 400">{{ l.what }}</div><span style="font-variant-numeric: tabular-nums">{{ l.amount }}</span>
      </div>
    </template>

    <div v-else style="padding: 12px">
      <DomainStatus domain="nordlys.no" status="pending" :records="[{ type: 'CNAME', name: 'www', value: 'sites.rootsquares.com' }]" />
    </div>
  </section>
</template>
