<script setup lang="ts">
import { computed } from 'vue'
import type { MembershipTypeOption } from '../../services/memberApi'
import { humanize } from '../../utils/formatEnum'
import { frequencyLabel } from '../../utils/membership'
import { withCurrency } from '../../utils/money'
import { activeLayout, type MembershipVariant } from '../layouts'
import LtButton from '../parts/LtButton.vue'

// Membership plans in the theme's variant (W9-R5): cards, rows or band. The square's own membership types and prices (Settings, Membership types).
const props = withDefaults(defineProps<{ items: MembershipTypeOption[]; title?: string; joinTo?: string; variant?: MembershipVariant }>(), { title: undefined, joinTo: '/membership', variant: undefined })
const v = computed(() => props.variant ?? activeLayout!.mem)
const price = (t: MembershipTypeOption) => (t.contact_for_price || t.price === null ? 'Ask us' : withCurrency(String(t.price)))
const unit = (t: MembershipTypeOption) => (t.contact_for_price || t.price === null ? '' : `per ${frequencyLabel(t.billing_frequency)}`)
const from = computed(() => {
  const prices = props.items.filter((t) => !t.contact_for_price && t.price !== null).map((t) => t.price as number)
  return prices.length ? withCurrency(String(Math.min(...prices))) : ''
})
</script>

<template>
  <p v-if="!items.length" class="lt-empty">Membership types will appear here.</p>

  <div v-else-if="v === 'cards'" class="lt-me-cards">
    <div v-for="(t, i) in items" :key="t.name" class="lt-plan" :class="{ 'lt-plan-hi': i === 1 || (items.length === 1) }">
      <small class="lt-kick">{{ humanize(t.name) }}</small>
      <b class="lt-plan-price">{{ price(t) }}<span v-if="unit(t)">{{ unit(t) }}</span></b>
      <p v-if="t.description" class="lt-plan-text">{{ t.description }}</p>
      <LtButton :to="joinTo" :kind="i === 1 || items.length === 1 ? 'w' : 'o'">Join now</LtButton>
    </div>
  </div>

  <div v-else-if="v === 'rows'" class="lt-me-rows">
    <div v-for="t in items" :key="t.name" class="lt-mr">
      <strong class="lt-mr-n">{{ humanize(t.name) }}</strong>
      <span class="lt-mute lt-mr-d lt-only-wide">{{ t.description }}</span>
      <span class="lt-mr-p">{{ price(t) }} <small v-if="unit(t)">{{ unit(t) }}</small></span>
      <router-link :to="joinTo" class="lt-mr-j lt-only-wide">Join →</router-link>
    </div>
  </div>

  <div v-else class="lt-me-band">
    <div class="lt-me-band-l">
      <small class="lt-kick">Membership<template v-if="from"> · from {{ from }}</template></small>
      <strong class="lt-me-band-t">{{ title || 'Become a member' }}</strong>
      <LtButton :to="joinTo" kind="w">Join now</LtButton>
    </div>
    <div class="lt-me-band-r">
      <div v-for="t in items" :key="t.name" class="lt-me-band-row"><b>{{ humanize(t.name) }}</b><span>{{ price(t) }}</span></div>
    </div>
  </div>
</template>
