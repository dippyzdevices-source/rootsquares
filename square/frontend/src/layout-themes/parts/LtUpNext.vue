<script setup lang="ts">
import { computed } from 'vue'
import { useSiteData } from '../useSiteData'
import { dayMonth, eventsOn, membershipOn } from '../useSiteLayout'
import { formatEventDate } from '../../utils/date'

// The "Up next" card of the heroes. Events on: the next event. Events off: a membership card. Both off: nothing (W9-R5 module rules).
const { nextEvent } = useSiteData()
const when = computed(() => (nextEvent.value ? dayMonth(nextEvent.value.start_datetime) : null))
</script>

<template>
  <router-link v-if="eventsOn && nextEvent && when" :to="`/events/${nextEvent.slug}`" class="lt-upnext">
    <span class="lt-upnext-date"><b>{{ when.day }}</b><i>{{ when.month }}</i></span>
    <span class="lt-upnext-body">
      <small>Up next</small>
      <strong>{{ nextEvent.title }}</strong>
      <span>{{ formatEventDate(nextEvent.start_datetime) }}<template v-if="nextEvent.venue"> · {{ nextEvent.venue }}</template></span>
    </span>
  </router-link>
  <router-link v-else-if="!eventsOn && membershipOn" to="/membership" class="lt-upnext">
    <span class="lt-upnext-body"><small>Membership open</small><strong>Join the community</strong><span>See how to become a member</span></span>
  </router-link>
</template>
