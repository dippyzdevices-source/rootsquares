<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useToast } from '@rootsquares/ui/components/useToast'
import { useTenantStore } from '@/stores/tenant'
import { useSite } from './useSite'
import TButton from './components/TButton.vue'

// Order confirmation (design "Order confirmation"): success when the treasurer has marked the order paid in the console, otherwise a
// warning that payment is not confirmed yet. Demo: "Add to calendar" downloads nothing.
const { t } = useI18n()
const route = useRoute()
const tenant = useTenantStore()
const { to } = useSite()
const { push } = useToast()
const c = computed(() => (tenant.checkout && String(tenant.checkout.id) === String(route.params.orderId) ? tenant.checkout : null))
const paid = computed(() => tenant.orders.find((o) => String(o.id) === String(route.params.orderId))?.status === 'paid')
</script>

<template>
  <section class="t-sec">
    <div class="t-wrap" style="max-width: 720px">
      <div v-if="!c" class="t-card"><p>{{ t('site.order.none') }}</p><TButton variant="outline" :to="to('/events')">{{ t('site.back') }}</TButton></div>
      <div v-else class="t-stack" style="gap: 20px">
        <div role="status" class="t-note" :class="paid ? 't-note--success' : 't-note--warning'" style="font-weight: 700; font-size: 18px">{{ paid ? t('site.order.confirmed') : t('site.order.waiting') }}</div>
        <h1 style="font-size: clamp(32px, 5vw, 46px); line-height: 1.1">{{ c.eventTitle }}</h1>
        <div class="t-card">
          <div class="t-muted" style="font-size: 13px">{{ t('site.order.orderNo') }}</div>
          <div class="t-ref__code">{{ c.ref }}</div>
          <div style="margin-top: 12px">{{ c.lines.map((l) => t('site.order.line', { qty: l.qty, label: l.label })).join(' · ') }} · {{ c.eventDate }} · {{ c.eventPlace }}</div>
          <p class="t-muted" style="margin: 12px 0 0">{{ paid ? t('site.order.confirmedText') : t('site.order.waitingText') }}</p>
        </div>
        <div class="t-row">
          <TButton @click="push(t('site.order.calAdded'), 'success')">{{ t('site.order.addCal') }}</TButton>
          <TButton variant="outline" :to="to('')">{{ t('site.order.back') }}</TButton>
        </div>
      </div>
    </div>
  </section>
</template>
