<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import BaseBadge from '../../components/ui/BaseBadge.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import SquareMark from '../../components/ui/SquareMark.vue'
import { squareProfile } from '../../services/squareConfig'
import { ticketStatusVariant } from '../../utils/ticketStatus'
import { useLookup } from '../../composables/useLookup'

export interface CarouselTicket {
  id: number
  ticketTypeName: string | null
  ticketCode: string
  status: string
  qrCodeDataUrl: string
}

const { label: ticketStatusLabel } = useLookup('ticket_status')
const props = defineProps<{ tickets: CarouselTicket[] }>()


const index = ref(0)

watch(
  () => props.tickets,
  () => {
    index.value = 0
  },
)

const current = computed(() => props.tickets[index.value] ?? null)

function showPrevious() {
  index.value = (index.value - 1 + props.tickets.length) % props.tickets.length
}

function showNext() {
  index.value = (index.value + 1) % props.tickets.length
}

const SWIPE_THRESHOLD_PX = 40
let touchStartX: number | null = null

function onTouchStart(event: TouchEvent) {
  touchStartX = event.touches[0]?.clientX ?? null
}

function onTouchEnd(event: TouchEvent) {
  if (touchStartX === null) return
  const touchEndX = event.changedTouches[0]?.clientX ?? touchStartX
  const delta = touchEndX - touchStartX
  if (delta > SWIPE_THRESHOLD_PX) {
    showPrevious()
  } else if (delta < -SWIPE_THRESHOLD_PX) {
    showNext()
  }
  touchStartX = null
}
</script>

<template>
  <div v-if="current" class="space-y-3">
    <div
      class="rounded-lg border border-border bg-black/5 p-4 text-center dark:bg-white/5"
      @touchstart="onTouchStart"
      @touchend="onTouchEnd"
    >
      <div class="mb-2 flex items-center justify-center gap-1.5">
        <SquareMark :size="20" />
        <span class="text-xs font-semibold text-text-secondary">{{ squareProfile.name }}</span>
      </div>
      <div class="relative mx-auto w-48">
        <img
          :src="current.qrCodeDataUrl"
          :alt="current.ticketCode"
          class="w-48"
          :class="{ 'opacity-30': current.status === 'used' }"
        />
        <div
          v-if="current.status === 'used'"
          class="absolute inset-0 flex items-center justify-center"
        >
          <span class="flex h-16 w-16 items-center justify-center rounded-full bg-success text-3xl text-white">
            &#10003;
          </span>
        </div>
      </div>
      <p class="mt-2 text-sm font-medium text-text">{{ current.ticketTypeName ?? 'Ticket' }}</p>
      <p class="text-xs text-text-secondary">{{ current.ticketCode }}</p>
      <BaseBadge :variant="ticketStatusVariant(current.status)" class="mt-1">
        {{ ticketStatusLabel(current.status) }}
      </BaseBadge>
    </div>

    <div v-if="tickets.length > 1" class="flex items-center justify-between">
      <BaseIconButton label="Previous ticket" size="sm" @click="showPrevious">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
      </BaseIconButton>
      <span class="text-xs text-text-secondary">{{ index + 1 }} / {{ tickets.length }}</span>
      <BaseIconButton label="Next ticket" size="sm" @click="showNext">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6" /></svg>
      </BaseIconButton>
    </div>
  </div>
</template>
