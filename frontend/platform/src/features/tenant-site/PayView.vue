<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { VIPPS_DEMO_NUMBER } from '@/mock/placeholders'
import { useTenantStore } from '@/stores/tenant'
import { useSite } from './useSite'
import TButton from './components/TButton.vue'
import TPlaceholder from './components/TPlaceholder.vue'

// Manual Vipps payment step (design tenant-themes-v2 components.md "Manual payment step"): Vipps number or QR, copyable reference,
// "I have paid" -> pending (warning) -> order page. The treasurer confirms in the console (Orders, Mark as paid). Demo: nothing is paid.
const { t, n } = useI18n()
const tenant = useTenantStore()
const { to } = useSite()
const c = computed(() => tenant.checkout)
const copied = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

async function copy() {
  try { await navigator.clipboard.writeText(c.value?.ref ?? '') } catch { /* clipboard unavailable: the reference stays selectable */ }
  copied.value = true
  clearTimeout(timer)
  timer = setTimeout(() => (copied.value = false), 1600)
}
function iPaid() { if (tenant.checkout) tenant.checkout.claimedPaid = true }
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <section class="t-sec">
    <div class="t-wrap">
      <h1 style="font-size: clamp(32px, 5vw, 46px); line-height: 1.1">{{ t('site.pay.title') }}</h1>
      <div v-if="!c" class="t-card" style="margin-top: 20px">
        <p>{{ t('site.pay.noOrder') }}</p>
        <TButton variant="outline" :to="to('/events')">{{ t('site.back') }}</TButton>
      </div>
      <div v-else class="t-detail" style="margin-top: 24px">
        <div class="t-card t-stack" style="gap: 18px">
          <p style="margin: 0">{{ t('site.pay.lead') }}</p>
          <div class="t-pay">
            <TPlaceholder ratio="1/1" shape="md" :label="t('site.pay.qr')" class="t-pay__qr" />
            <div style="min-width: 0">
              <div class="t-eyebrow">Vipps</div>
              <div class="t-pay__num">{{ VIPPS_DEMO_NUMBER }}</div>
              <div>{{ t('site.pay.to', { name: tenant.name }) }}</div>
            </div>
          </div>
          <div class="t-ref">
            <div><div class="t-muted" style="font-size: 13px">{{ t('site.pay.ref') }}</div><div class="t-ref__code">{{ c.ref }}</div></div>
            <button type="button" class="t-btn t-btn--outline" :aria-label="t('site.pay.copyRef')" @click="copy">{{ copied ? t('bx.copied') : t('bx.copy') }}</button>
          </div>
          <TButton v-if="!c.claimedPaid" block @click="iPaid">{{ t('site.pay.iPaid') }}</TButton>
          <template v-else>
            <div role="status" class="t-note t-note--warning"><b>{{ t('site.pay.pendingTitle') }}</b><div>{{ t('site.pay.pendingText') }}</div></div>
            <div><TButton variant="outline" :to="to(`/order/${c.id}`)">{{ t('site.pay.viewOrder') }}</TButton></div>
          </template>
          <p class="t-muted" style="margin: 0; font-size: 14px">{{ t('site.pay.demo') }}</p>
        </div>
        <div class="t-card t-card--sunken">
          <h2 style="font-size: 22px; margin-bottom: 12px">{{ t('site.pay.summary') }}</h2>
          <div v-for="l in c.lines" :key="l.label" class="t-sum"><span>{{ t('site.order.line', { qty: l.qty, label: l.label }) }}</span><span class="t-strong">NOK {{ n(l.qty * l.price) }}</span></div>
          <div class="t-sum"><span>{{ t('site.fee') }}</span><span class="t-strong">NOK {{ c.fee }}</span></div>
          <div class="t-sum t-sum--total"><span>{{ t('site.total') }}</span><span>NOK {{ n(c.total) }}</span></div>
        </div>
      </div>
    </div>
  </section>
</template>
