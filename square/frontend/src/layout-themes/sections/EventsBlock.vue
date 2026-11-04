<script setup lang="ts">
import { computed } from 'vue'
import { useLookup } from '../../composables/useLookup'
import type { EventSummary } from '../../services/eventsApi'
import { formatEventDate } from '../../utils/date'
import { dayMonth, timeOf } from '../useSiteLayout'
import { activeLayout, type EventsVariant } from '../layouts'
import LtPhoto from '../parts/LtPhoto.vue'

// The programme in the theme's variant (W9-R5): list, cards, timeline, table, giant, strip, notes or media. Real events; nothing invented.
const props = defineProps<{ items: EventSummary[]; variant?: EventsVariant; chips?: boolean }>()
const v = computed(() => props.variant ?? activeLayout!.ev)
const { label: typeLabel } = useLookup('event_type')
const to = (e: EventSummary) => `/events/${e.slug}`
const title = (e: EventSummary) => (e.published === false ? `Draft · ${e.title}` : e.title)
</script>

<template>
  <p v-if="!items.length" class="lt-empty">No upcoming events. Check back soon.</p>

  <div v-else-if="v === 'list'" class="lt-ev-list">
    <router-link v-for="e in items" :key="e.id" :to="to(e)" class="lt-ev-row">
      <span class="lt-ev-date"><b>{{ dayMonth(e.start_datetime).day }}</b><i>{{ dayMonth(e.start_datetime).month }}</i></span>
      <span class="lt-ev-main"><span v-if="e.event_type" class="lt-ev-chips"><em class="lt-ev-chip">{{ typeLabel(e.event_type) }}</em></span><strong>{{ title(e) }}</strong><small v-if="e.short_description" class="lt-ev-desc">{{ e.short_description }}</small><small class="lt-only-narrow">{{ e.venue }}</small></span>
      <span class="lt-ev-venue lt-only-wide">{{ e.venue }}</span>
      <span class="lt-ev-go lt-only-wide" aria-hidden="true">→</span>
    </router-link>
  </div>

  <div v-else-if="v === 'cards'" class="lt-ev-cards">
    <router-link v-for="e in items.slice(0, 6)" :key="e.id" :to="to(e)" class="lt-card">
      <LtPhoto :src="e.banner_image" :alt="e.title" ratio="16 / 10" radius="0" />
      <span class="lt-card-body">
        <small class="lt-kick">{{ dayMonth(e.start_datetime).day }} {{ dayMonth(e.start_datetime).month }} · {{ typeLabel(e.event_type) }}</small>
        <strong class="lt-card-title">{{ title(e) }}</strong>
        <span v-if="e.venue" class="lt-mute">{{ e.venue }}</span>
      </span>
    </router-link>
  </div>

  <div v-else-if="v === 'timeline'" class="lt-ev-timeline">
    <router-link v-for="(e, i) in items" :key="e.id" :to="to(e)" class="lt-tl-row" :class="{ 'lt-tl-flip': i % 2 === 1 }">
      <span class="lt-tl-dot" aria-hidden="true" />
      <span class="lt-tl-when"><em>{{ dayMonth(e.start_datetime).day }} {{ dayMonth(e.start_datetime).month }}</em><small>{{ timeOf(e.start_datetime) }}</small></span>
      <span class="lt-tl-what"><strong>{{ title(e) }}</strong><span v-if="e.venue" class="lt-mute">{{ e.venue }}</span></span>
    </router-link>
  </div>

  <div v-else-if="v === 'table'" class="lt-ev-table">
    <div class="lt-ev-thead lt-only-wide"><span>Date</span><span>Event</span><span>Venue</span><span>Type</span><span>Time</span></div>
    <router-link v-for="e in items" :key="e.id" :to="to(e)" class="lt-ev-trow">
      <span class="lt-num">{{ dayMonth(e.start_datetime).day }} {{ dayMonth(e.start_datetime).month }}</span>
      <span class="lt-ev-ttl">{{ e.title }}</span>
      <span class="lt-mute lt-only-wide">{{ e.venue }}</span>
      <span class="lt-acc-i lt-only-wide">{{ typeLabel(e.event_type) }}</span>
      <span class="lt-mute lt-num lt-only-wide">{{ timeOf(e.start_datetime) }}</span>
    </router-link>
  </div>

  <div v-else-if="v === 'tiles'" class="lt-ev-tiles">
    <router-link v-for="(e, i) in items" :key="e.id" :to="to(e)" class="lt-tile" :style="{ background: `var(--lt-t${i % 3}-bg)`, color: `var(--lt-t${i % 3}-fg)` }">
      <span class="lt-tile-day">{{ dayMonth(e.start_datetime).day }}</span>
      <small class="lt-tile-kick">{{ dayMonth(e.start_datetime).month }} · {{ typeLabel(e.event_type) }}</small>
      <strong class="lt-tile-title">{{ title(e) }}</strong>
      <span class="lt-tile-meta">{{ e.venue }}<template v-if="e.venue"> · </template>{{ timeOf(e.start_datetime) }}</span>
    </router-link>
  </div>

  <div v-else-if="v === 'neu'" class="lt-ev-neu">
    <router-link v-for="e in items" :key="e.id" :to="to(e)" class="lt-neu-card lt-nu">
      <span class="lt-neu-date lt-nui-6"><b>{{ dayMonth(e.start_datetime).day }}</b><i>{{ dayMonth(e.start_datetime).month }}</i></span>
      <span class="lt-neu-main"><small class="lt-kick">{{ typeLabel(e.event_type) }}</small><strong>{{ title(e) }}</strong><span class="lt-mute">{{ e.venue }}<template v-if="e.venue"> · </template>{{ timeOf(e.start_datetime) }}</span></span>
    </router-link>
  </div>

  <div v-else-if="v === 'datarows'" class="lt-ev-data">
    <div class="lt-dr-head lt-only-wide"><span>Date</span><span>Event</span><span>Venue</span><span>Type</span><span>Time</span></div>
    <router-link v-for="(e, i) in items" :key="e.id" :to="to(e)" class="lt-dr-row">
      <span class="lt-num lt-dr-date">{{ dayMonth(e.start_datetime).day }} {{ dayMonth(e.start_datetime).month }}</span>
      <span class="lt-dr-ttl">{{ title(e) }}</span>
      <span class="lt-mute lt-only-wide">{{ e.venue }}</span>
      <span class="lt-only-wide"><span class="lt-chip" :class="{ 'lt-chip-hi': i === 0 }">{{ typeLabel(e.event_type) }}</span></span>
      <span class="lt-mute lt-num lt-only-wide">{{ timeOf(e.start_datetime) }}</span>
    </router-link>
  </div>

  <div v-else-if="v === 'agenda'" class="lt-ev-agenda">
    <router-link v-for="(e, i) in items" :key="e.id" :to="to(e)" class="lt-ag-row">
      <span class="lt-ag-when"><b>{{ dayMonth(e.start_datetime).day }} {{ dayMonth(e.start_datetime).month }}</b><small>{{ timeOf(e.start_datetime) }}</small></span>
      <span class="lt-ag-rail"><i class="lt-ag-dot" :class="{ 'is-first': i === 0 }">{{ i === 0 ? '✓' : '' }}</i><i v-if="i < items.length - 1" class="lt-ag-line" /></span>
      <span class="lt-ag-card"><span class="lt-ag-main"><strong>{{ title(e) }}</strong><small>{{ e.venue }}<template v-if="e.venue"> · </template>{{ typeLabel(e.event_type) }}</small></span><span class="lt-mute" aria-hidden="true">›</span></span>
    </router-link>
  </div>

  <div v-else-if="v === 'round'" class="lt-ev-round lt-on-panel">
    <router-link v-for="e in items.slice(0, 4)" :key="e.id" :to="to(e)" class="lt-ro-item">
      <LtPhoto :src="e.banner_image" :alt="e.title" ratio="1" radius="50%" class="lt-ro-pic" />
      <strong class="lt-ro-t">{{ title(e) }}</strong>
      <span class="lt-ro-m">{{ dayMonth(e.start_datetime).day }} {{ dayMonth(e.start_datetime).month }}<template v-if="e.venue"> · {{ e.venue }}</template></span>
      <span class="lt-ro-chip">{{ typeLabel(e.event_type) }}</span>
    </router-link>
  </div>

  <div v-else-if="v === 'blobs'" class="lt-ev-blobs">
    <router-link v-for="(e, i) in items" :key="e.id" :to="to(e)" class="lt-bl-item">
      <LtPhoto :src="e.banner_image" :alt="e.title" ratio="1 / 0.86" :class="`lt-blob-${i % 4}`" />
      <span class="lt-bl-text"><small class="lt-bl-kick">{{ dayMonth(e.start_datetime).day }} {{ dayMonth(e.start_datetime).month }} · {{ typeLabel(e.event_type) }}</small><strong>{{ title(e) }}</strong><em v-if="e.venue">{{ e.venue }}</em></span>
    </router-link>
  </div>

  <div v-else-if="v === 'bento'" class="lt-ev-bento">
    <router-link v-for="(e, i) in items" :key="e.id" :to="to(e)" class="lt-bento-ev" :class="{ 'lt-bento-big': i % 5 === 0, 'lt-bento-wide': i % 5 === 3 }">
      <LtPhoto :src="e.banner_image" :alt="e.title" class="lt-bento-pic" radius="0" />
      <span class="lt-bento-shade" aria-hidden="true" />
      <span class="lt-bento-text">
        <small>{{ dayMonth(e.start_datetime).day }} {{ dayMonth(e.start_datetime).month }} · {{ typeLabel(e.event_type) }}</small>
        <strong>{{ title(e) }}</strong>
        <span v-if="e.venue">{{ e.venue }}</span>
      </span>
    </router-link>
  </div>

  <div v-else-if="v === 'giant'" class="lt-ev-giant">
    <router-link v-for="(e, i) in items" :key="e.id" :to="to(e)" class="lt-gi-row" :class="{ 'lt-gi-first': i === 0 }">
      <span class="lt-gi-day">{{ dayMonth(e.start_datetime).day }}</span>
      <span class="lt-gi-main"><strong>{{ title(e) }}</strong><small class="lt-mono">{{ dayMonth(e.start_datetime).month }}<template v-if="e.venue"> · {{ e.venue }}</template></small></span>
      <span class="lt-gi-time lt-only-wide">{{ timeOf(e.start_datetime) }}</span>
    </router-link>
  </div>

  <div v-else-if="v === 'strip'" class="lt-ev-strip">
    <router-link v-for="e in items" :key="e.id" :to="to(e)" class="lt-st-item">
      <span class="lt-st-pic">
        <LtPhoto :src="e.banner_image" :alt="e.title" ratio="3 / 4" />
        <span class="lt-st-date"><b>{{ dayMonth(e.start_datetime).day }}</b><i>{{ dayMonth(e.start_datetime).month }}</i></span>
      </span>
      <strong class="lt-card-title">{{ title(e) }}</strong>
      <span v-if="e.venue" class="lt-mute">{{ e.venue }}</span>
    </router-link>
  </div>

  <div v-else-if="v === 'notes'" class="lt-ev-notes">
    <router-link v-for="(e, i) in items" :key="e.id" :to="to(e)" class="lt-note" :class="`lt-note-${i % 4}`">
      <span class="lt-tape" aria-hidden="true" />
      <span class="lt-hand-n">{{ dayMonth(e.start_datetime).day }} {{ dayMonth(e.start_datetime).month }}</span>
      <strong class="lt-card-title">{{ title(e) }}</strong>
      <span class="lt-mute">{{ e.venue }}<template v-if="e.venue"> · </template>{{ timeOf(e.start_datetime) }}</span>
    </router-link>
  </div>

  <div v-else class="lt-ev-media">
    <router-link v-for="e in items" :key="e.id" :to="to(e)" class="lt-me-row">
      <LtPhoto :src="e.banner_image" :alt="e.title" ratio="4 / 3" />
      <span class="lt-me-main">
        <small class="lt-kick">{{ formatEventDate(e.start_datetime) }} · {{ typeLabel(e.event_type) }}</small>
        <strong class="lt-me-title">{{ title(e) }}</strong>
        <span v-if="e.venue" class="lt-mute">{{ e.venue }}</span>
      </span>
      <span class="lt-ev-go lt-only-wide" aria-hidden="true">→</span>
    </router-link>
  </div>
</template>
