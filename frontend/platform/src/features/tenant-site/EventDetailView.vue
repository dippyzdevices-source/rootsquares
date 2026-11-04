<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { placeOrder } from '@/services/api'
import { useTenantStore } from '@/stores/tenant'
import { useSite } from './useSite'
import TButton from './components/TButton.vue'
import TField from './components/TField.vue'
import TPlaceholder from './components/TPlaceholder.vue'

// Event detail with ticket selection. A placed order appears in the console under Orders as awaiting payment.
const { t, n } = useI18n()
const route = useRoute()
const router = useRouter()
const tenant = useTenantStore()
const { to } = useSite()

const event = computed(() => tenant.events.find((e) => e.id === route.params.eventId))
const qty = reactive<Record<string, number>>({})
const buyer = reactive({ name: '', email: '' })
const touched = ref(false)
const busy = ref(false)

const subtotal = computed(() => event.value?.tickets.reduce((s, x) => s + x.price * (qty[x.id] ?? 0), 0) ?? 0)
const count = computed(() => Object.values(qty).reduce((s, v) => s + v, 0))
const fee = computed(() => (subtotal.value > 0 ? 10 : 0))
const errors = computed(() => ({
  name: buyer.name.trim() ? '' : t('site.joinNameError'),
  email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(buyer.email) ? '' : t('site.joinEmailError'),
  tickets: count.value > 0 ? '' : t('site.chooseTickets'),
}))
const set = (id: string, v: number) => { qty[id] = Math.max(0, v) }
const priceLabel = (p: number) => (p === 0 ? t('site.free') : `NOK ${p} ${t('site.each')}`)

async function reserve() {
  touched.value = true
  const e = event.value
  if (!e || errors.value.name || errors.value.email || errors.value.tickets) return
  busy.value = true
  const total = subtotal.value + fee.value
  await placeOrder(e.id, total)
  const id = Math.max(...tenant.orders.map((o) => o.id)) + 1
  tenant.orders.unshift({ id, name: buyer.name.trim(), eventId: e.id, event: e.title, total, status: 'pending', date: new Date().toISOString().slice(0, 10) })
  busy.value = false
  const lines = e.tickets.filter((x) => (qty[x.id] ?? 0) > 0).map((x) => ({ label: x.label, qty: qty[x.id]!, price: x.price }))
  const ymd = new Date().toISOString().slice(2, 7).replace('-', '')
  tenant.checkout = { id, ref: `EVT-${ymd}-${String(id).padStart(4, '0')}`, eventId: e.id, eventTitle: e.title, eventDate: e.dateLabel, eventPlace: e.place, lines, subtotal: subtotal.value, fee: fee.value, total, claimedPaid: false }
  router.push(to(`/events/${e.id}/pay`))
}
</script>

<template>
  <section class="t-sec">
    <div class="t-wrap">
      <p style="margin: 0 0 16px"><RouterLink :to="to('/events')">← {{ t('site.back') }}</RouterLink></p>
      <h1 v-if="!event" style="font-size: 32px">{{ t('site.notFound') }}</h1>
      <div v-else class="t-detail">
        <div class="t-stack" style="gap: 20px">
          <TPlaceholder ratio="16/9" shape="lg" label="photo · event" />
          <div><span class="t-badge">{{ event.tag }}</span></div>
          <h1 style="font-size: clamp(32px, 5vw, 46px); line-height: 1.1">{{ event.title }}</h1>
          <p class="t-muted" style="margin: 0; font-size: 17px">{{ event.dateLabel }}<br>{{ event.place }}</p>
          <p style="margin: 0; font-size: 17px">{{ event.summary }}</p>
          <p class="t-muted" style="margin: 0">{{ t('site.sold', { sold: event.sold, capacity: event.capacity }) }}</p>
        </div>
        <div class="t-card t-card--sunken">
          <form class="t-stack" novalidate @submit.prevent="reserve">
            <h2 style="font-size: 24px">{{ t('site.yourOrder') }}</h2>
            <div>
              <div v-for="x in event.tickets" :key="x.id" class="t-ticket">
                <div><b>{{ x.label }}</b><small>{{ priceLabel(x.price) }}</small></div>
                <div class="t-qty">
                  <button type="button" :aria-label="`${t('common.back')} ${x.label}`" @click="set(x.id, (qty[x.id] ?? 0) - 1)">−</button>
                  <span aria-live="polite">{{ qty[x.id] ?? 0 }}</span>
                  <button type="button" :aria-label="`${t('common.add')} ${x.label}`" @click="set(x.id, (qty[x.id] ?? 0) + 1)">+</button>
                </div>
              </div>
              <span v-if="touched && errors.tickets" class="t-error"><span aria-hidden="true">× </span>{{ errors.tickets }}</span>
            </div>
            <TField v-model="buyer.name" :label="t('site.joinName')" autocomplete="name" :error="touched ? errors.name : ''" />
            <TField v-model="buyer.email" type="email" :label="t('site.joinEmail')" autocomplete="email" :error="touched ? errors.email : ''" />
            <div>
              <div class="t-sum"><span>{{ t('site.subtotal') }}</span><span>NOK {{ n(subtotal) }}</span></div>
              <div class="t-sum"><span>{{ t('site.fee') }}</span><span>NOK {{ fee }}</span></div>
              <div class="t-sum t-sum--total"><span>{{ t('site.total') }}</span><span>NOK {{ n(subtotal + fee) }}</span></div>
            </div>
            <TButton type="submit" block :disabled="busy">{{ busy ? t('site.reserving') : t('site.reserve') }}</TButton>
            <p class="t-muted" style="margin: 0; font-size: 14px">{{ t('site.orderNote') }}</p>
          </form>
        </div>
      </div>
    </div>
  </section>
</template>
