<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import BaseButton from './BaseButton.vue'
import BaseModal from './BaseModal.vue'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    file: File | null
    /** width / height — e.g. 1 for a square (member avatars), 0.75 for a 3:4 portrait
     * rectangle (committee portraits). Defaults to 1, so every existing caller is unaffected. */
    aspectRatio?: number
  }>(),
  { aspectRatio: 1 },
)

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  cropped: [blob: Blob]
}>()

// The larger of the two viewport/output dimensions is capped at this reference value; the
// other is derived from aspectRatio, so a square (ratio 1) behaves exactly as before and a
// portrait ratio (<1) produces a taller-than-wide crop box instead.
const VIEWPORT_REF = 260
const OUTPUT_REF = 512
const VIEWPORT_WIDTH = computed(() => Math.round(props.aspectRatio >= 1 ? VIEWPORT_REF : VIEWPORT_REF * props.aspectRatio))
const VIEWPORT_HEIGHT = computed(() => Math.round(props.aspectRatio >= 1 ? VIEWPORT_REF / props.aspectRatio : VIEWPORT_REF))
const OUTPUT_WIDTH = computed(() => Math.round(props.aspectRatio >= 1 ? OUTPUT_REF : OUTPUT_REF * props.aspectRatio))
const OUTPUT_HEIGHT = computed(() => Math.round(props.aspectRatio >= 1 ? OUTPUT_REF / props.aspectRatio : OUTPUT_REF))

const imgRef = ref<HTMLImageElement | null>(null)
const imageUrl = ref<string | null>(null)
const naturalWidth = ref(0)
const naturalHeight = ref(0)
const zoom = ref(1)
const panX = ref(0)
const panY = ref(0)
const dragging = ref(false)

let dragStartX = 0
let dragStartY = 0
let panStartX = 0
let panStartY = 0

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

const baseScale = computed(() => {
  if (!naturalWidth.value || !naturalHeight.value) return 0
  return Math.max(VIEWPORT_WIDTH.value / naturalWidth.value, VIEWPORT_HEIGHT.value / naturalHeight.value)
})
const displayedWidth = computed(() => naturalWidth.value * baseScale.value * zoom.value)
const displayedHeight = computed(() => naturalHeight.value * baseScale.value * zoom.value)
const centerX = computed(() => (VIEWPORT_WIDTH.value - displayedWidth.value) / 2)
const centerY = computed(() => (VIEWPORT_HEIGHT.value - displayedHeight.value) / 2)
const minTranslateX = computed(() => Math.min(0, VIEWPORT_WIDTH.value - displayedWidth.value))
const minTranslateY = computed(() => Math.min(0, VIEWPORT_HEIGHT.value - displayedHeight.value))
const translateX = computed(() => clamp(centerX.value + panX.value, minTranslateX.value, 0))
const translateY = computed(() => clamp(centerY.value + panY.value, minTranslateY.value, 0))

const imageReady = computed(() => naturalWidth.value > 0 && naturalHeight.value > 0)

const imageStyle = computed(() => ({
  width: `${displayedWidth.value}px`,
  height: `${displayedHeight.value}px`,
  transform: `translate(${translateX.value}px, ${translateY.value}px)`,
}))

function resetTransform() {
  zoom.value = 1
  panX.value = 0
  panY.value = 0
  naturalWidth.value = 0
  naturalHeight.value = 0
}

watch(
  () => props.file,
  (file) => {
    if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
    resetTransform()
    imageUrl.value = file ? URL.createObjectURL(file) : null
  },
  { immediate: true },
)

onUnmounted(() => {
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  stopDrag()
})

function onImageLoad() {
  if (!imgRef.value) return
  naturalWidth.value = imgRef.value.naturalWidth
  naturalHeight.value = imgRef.value.naturalHeight
}

function pointerPos(event: MouseEvent | TouchEvent): { x: number; y: number } {
  if ('touches' in event) {
    const touch = event.touches[0] ?? event.changedTouches[0]
    return { x: touch?.clientX ?? 0, y: touch?.clientY ?? 0 }
  }
  return { x: event.clientX, y: event.clientY }
}

function startDrag(event: MouseEvent | TouchEvent) {
  if (!imageReady.value) return
  dragging.value = true
  const pos = pointerPos(event)
  dragStartX = pos.x
  dragStartY = pos.y
  panStartX = panX.value
  panStartY = panY.value
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
  window.addEventListener('touchmove', onDrag)
  window.addEventListener('touchend', stopDrag)
}

function onDrag(event: MouseEvent | TouchEvent) {
  if (!dragging.value) return
  const pos = pointerPos(event)
  panX.value = panStartX + (pos.x - dragStartX)
  panY.value = panStartY + (pos.y - dragStartY)
}

function stopDrag() {
  dragging.value = false
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
  window.removeEventListener('touchmove', onDrag)
  window.removeEventListener('touchend', stopDrag)
}

function cancel() {
  emit('update:modelValue', false)
}

function save() {
  const img = imgRef.value
  if (!img || !imageReady.value) return

  const effectiveScale = baseScale.value * zoom.value
  const srcWidth = VIEWPORT_WIDTH.value / effectiveScale
  const srcHeight = VIEWPORT_HEIGHT.value / effectiveScale
  const srcX = clamp(-translateX.value / effectiveScale, 0, naturalWidth.value - srcWidth)
  const srcY = clamp(-translateY.value / effectiveScale, 0, naturalHeight.value - srcHeight)

  const canvas = document.createElement('canvas')
  canvas.width = OUTPUT_WIDTH.value
  canvas.height = OUTPUT_HEIGHT.value
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.drawImage(img, srcX, srcY, srcWidth, srcHeight, 0, 0, OUTPUT_WIDTH.value, OUTPUT_HEIGHT.value)
  canvas.toBlob(
    (blob) => {
      if (blob) emit('cropped', blob)
    },
    'image/jpeg',
    0.92,
  )
}
</script>

<template>
  <BaseModal :model-value="modelValue" title="Crop your photo" @update:model-value="cancel">
    <div style="display: flex; flex-direction: column; align-items: center; gap: var(--ds-space-4)">
      <div
        class="ds-crop-viewport"
        :style="{ width: `${VIEWPORT_WIDTH}px`, height: `${VIEWPORT_HEIGHT}px` }"
        @mousedown="startDrag"
        @touchstart="startDrag"
      >
        <img
          v-if="imageUrl"
          ref="imgRef"
          :src="imageUrl"
          class="ds-crop-image"
          :style="imageStyle"
          draggable="false"
          alt=""
          @load="onImageLoad"
        />
      </div>
      <label class="ds-field" style="width: 100%">
        <span class="ds-field-label">Zoom</span>
        <input v-model.number="zoom" type="range" min="1" max="3" step="0.01" class="ds-range" :disabled="!imageReady" />
      </label>
      <p class="ds-caption">Drag to reposition, use the slider to zoom.</p>
    </div>
    <div style="margin-top: var(--ds-space-5); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
      <BaseButton type="button" variant="secondary" @click="cancel">Cancel</BaseButton>
      <BaseButton type="button" :disabled="!imageReady" @click="save">Save photo</BaseButton>
    </div>
  </BaseModal>
</template>
