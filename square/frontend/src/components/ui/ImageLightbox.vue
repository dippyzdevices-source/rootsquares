<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseModal from './BaseModal.vue'

// Photo viewer matching the event page's lightbox (EventDetailView.vue): modal hugs the photo,
// scrim icon arrows + dots overlaid on its edges, click-to-zoom, touch swipe. `index` is
// v-model-able so the opener chooses the starting photo.
const props = defineProps<{
  modelValue: boolean
  images: string[]
  index: number
  alt: string
  // Optional caption shown under the photo (gallery photos carry one).
  caption?: string | null
}>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; 'update:index': [value: number] }>()

const zoomed = ref(false)
const hasMany = computed(() => props.images.length > 1)
const current = computed(() => props.images[props.index] ?? null)
// Dots suit a handful of photos; a long album gets an "n / N" counter instead.
const MAX_DOTS = 12
const showDots = computed(() => props.images.length <= MAX_DOTS)

watch(() => [props.index, props.modelValue], () => (zoomed.value = false))

function step(delta: number) {
  const count = props.images.length
  if (!count) return
  emit('update:index', (props.index + delta + count) % count)
}

const SWIPE_THRESHOLD_PX = 40
let touchStartX: number | null = null

function onTouchStart(event: TouchEvent) {
  touchStartX = event.touches[0]?.clientX ?? null
}

function onTouchEnd(event: TouchEvent) {
  if (touchStartX === null || !hasMany.value) return
  const delta = (event.changedTouches[0]?.clientX ?? touchStartX) - touchStartX
  if (delta > SWIPE_THRESHOLD_PX) step(-1)
  else if (delta < -SWIPE_THRESHOLD_PX) step(1)
  touchStartX = null
}

const frameStyle = {
  width: '100%',
  maxHeight: '80vh',
  overflow: 'auto',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'var(--ds-surface-sunken)',
  borderRadius: 'var(--ds-radius-md)',
  touchAction: 'pan-y pinch-zoom',
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    size="xl"
    hug-content
    aria-label="Photo viewer"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="current" style="position: relative">
      <div :style="frameStyle" @touchstart="onTouchStart" @touchend="onTouchEnd">
        <img
          :src="current"
          :alt="alt"
          :style="{
            cursor: zoomed ? 'zoom-out' : 'zoom-in',
            transform: zoomed ? 'scale(2)' : 'scale(1)',
            transition: 'transform 150ms ease',
            maxWidth: '100%',
            maxHeight: '80vh',
            display: 'block',
          }"
          @click="zoomed = !zoomed"
        />
      </div>
      <template v-if="hasMany">
        <button
          type="button"
          class="ds-icon-btn ds-icon-btn-scrim"
          aria-label="Previous photo" title="Previous photo"
          style="position: absolute; top: 50%; left: var(--ds-space-3); transform: translateY(-50%)"
          @click.stop="step(-1)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
        </button>
        <button
          type="button"
          class="ds-icon-btn ds-icon-btn-scrim"
          aria-label="Next photo" title="Next photo"
          style="position: absolute; top: 50%; right: var(--ds-space-3); transform: translateY(-50%)"
          @click.stop="step(1)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6" /></svg>
        </button>
        <div v-if="showDots" class="ds-dot-bar" style="position: absolute; bottom: var(--ds-space-3); left: 50%; transform: translateX(-50%)">
          <button
            v-for="(image, dotIndex) in images"
            :key="image + dotIndex"
            type="button"
            class="ds-testimonial-dot"
            :class="{ 'ds-testimonial-dot-active': dotIndex === index }"
            :aria-label="`Go to photo ${dotIndex + 1}`"
            @click.stop="emit('update:index', dotIndex)"
          />
        </div>
        <span
          v-else
          class="ds-meta"
          style="position: absolute; bottom: var(--ds-space-3); left: 50%; transform: translateX(-50%); padding: 2px var(--ds-space-3); border-radius: var(--ds-radius-pill); background: rgba(0, 0, 0, 0.55); color: #fff"
        >{{ index + 1 }} / {{ images.length }}</span>
      </template>
      <p v-if="caption" class="ds-meta ds-desc-s" style="margin-top: var(--ds-space-3)">{{ caption }}</p>
    </div>
  </BaseModal>
</template>
