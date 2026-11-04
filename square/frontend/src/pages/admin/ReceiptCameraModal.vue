<script setup lang="ts">
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import { createCameraCapture, type CameraCaptureHandle, type CameraOption } from '../../utils/cameraCapture'

// A live in-browser camera capture, the same underlying idea as the check-in scanner's own
// camera use (a real getUserMedia video feed, not delegating to the OS's separate camera app
// via <input capture> — which several desktop/mobile browser combinations silently ignore,
// falling back to a plain file-browse dialog).
const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; captured: [file: File] }>()

const videoEl = ref<HTMLVideoElement | null>(null)
const error = ref<string | null>(null)
const starting = ref(true)
const cameras = ref<CameraOption[]>([])
const selectedCameraId = ref('')
let camera: CameraCaptureHandle | null = null
let switchingCamera = false

const cameraOptions = computed(() => [
  { value: '', label: 'Default camera' },
  ...cameras.value.map((c) => ({ value: c.id, label: c.label })),
])

async function startCamera() {
  error.value = null
  starting.value = true
  try {
    if (videoEl.value) {
      camera = createCameraCapture(videoEl.value)
      await camera.start()

      try {
        cameras.value = await camera.listCameras()
      } catch {
        // Camera picker is a convenience — a browser that can't enumerate devices just keeps
        // using whatever camera already started (same precedent as qrScanner.ts's consumer).
      }
    }
  } catch {
    error.value = "Couldn't access the camera. Check your browser's camera permission, or choose a file instead."
  } finally {
    starting.value = false
  }
}

function stopCamera() {
  camera?.stop()
  camera = null
  cameras.value = []
  selectedCameraId.value = ''
}

async function capturePhoto() {
  if (!camera) return
  try {
    const file = await camera.capture(`receipt-${Date.now()}.jpg`)
    emit('captured', file)
    close()
  } catch {
    error.value = "Couldn't capture the photo. Please try again."
  }
}

function close() {
  stopCamera()
  emit('update:modelValue', false)
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      await nextTick() // the <video> only exists once BaseModal's Teleported content mounts
      await startCamera()
    } else {
      stopCamera()
    }
  },
)

watch(selectedCameraId, async (cameraId) => {
  if (!cameraId || !camera || switchingCamera) return
  switchingCamera = true
  try {
    await camera.setCamera(cameraId)
  } catch {
    // Switching cameras can fail transiently (e.g. the device was unplugged) — the previously
    // active camera keeps running either way.
  } finally {
    switchingCamera = false
  }
})

onUnmounted(stopCamera)
</script>

<template>
  <BaseModal :model-value="modelValue" title="Take a photo" @update:model-value="close">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
      <div v-if="error" class="ds-alert ds-alert-danger"><div>{{ error }}</div></div>
      <video
        ref="videoEl"
        autoplay
        playsinline
        muted
        style="width: 100%; max-height: 60vh; border-radius: var(--ds-radius-md); background: #000"
      />
      <BaseSelect v-if="cameras.length > 1" v-model="selectedCameraId" :options="cameraOptions" />
      <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="close">Cancel</BaseButton>
        <BaseButton type="button" :disabled="starting || !!error" @click="capturePhoto">Capture</BaseButton>
      </div>
    </div>
  </BaseModal>
</template>
