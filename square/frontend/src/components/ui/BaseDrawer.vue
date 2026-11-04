<script setup lang="ts">
import { onUnmounted, watch } from 'vue'

const props = withDefaults(
  defineProps<{ modelValue: boolean; title?: string; side?: 'left' | 'right' }>(),
  { side: 'right' },
)
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

function close() {
  emit('update:modelValue', false)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') close()
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      document.addEventListener('keydown', onKeydown)
    } else {
      document.removeEventListener('keydown', onKeydown)
    }
  },
  { immediate: true },
)

onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <div v-if="modelValue" class="fixed inset-0 z-50">
      <div class="absolute inset-0 bg-black/40" @click="close" />
      <div
        class="absolute top-0 h-full w-full max-w-sm bg-surface p-6 shadow-lg"
        :class="side === 'right' ? 'right-0' : 'left-0'"
      >
        <div class="mb-4 flex items-center justify-between">
          <h2 v-if="title" class="text-lg font-semibold text-text">{{ title }}</h2>
          <button
            type="button"
            aria-label="Close"
            class="text-text-secondary hover:text-text"
            @click="close"
          >
            &#10005;
          </button>
        </div>
        <slot />
      </div>
    </div>
  </Teleport>
</template>
