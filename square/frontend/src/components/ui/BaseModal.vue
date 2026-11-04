<script setup lang="ts">
import { onUnmounted, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title?: string
    ariaLabel?: string
    size?: 'md' | 'lg' | 'xl'
    hugContent?: boolean
  }>(),
  { size: 'md', hugContent: false },
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
    <!-- ds-scope on the overlay itself: Teleport moves this subtree to document.body, outside
         whatever .ds-scope wrapper the calling page has — without its own .ds-scope class here,
         every --ds-* custom property a modal's contents rely on would resolve to nothing. -->
    <div v-if="modelValue" class="ds-scope ds-modal-overlay" role="presentation" @click="close">
      <div
        role="dialog"
        aria-modal="true"
        :aria-label="!title ? (ariaLabel ?? 'Dialog') : undefined"
        class="ds-modal"
        :class="[
          size === 'lg' ? 'ds-modal-lg' : '',
          size === 'xl' ? 'ds-modal-xl' : '',
          !title ? 'ds-modal-untitled' : '',
          hugContent ? 'ds-modal-hug' : '',
        ]"
        @click.stop
      >
        <!-- A title-less modal (an image/receipt viewer, not a labeled dialog) skips the
             sunken .ds-modal-head band entirely rather than rendering it empty save for the
             close button — that read as a bulky, pointless bar. Its close button instead
             floats over the slot content itself, same icon/classes as the titled case. -->
        <div v-if="title" class="ds-modal-head">
          <h2 class="ds-modal-title">{{ title }}</h2>
          <button type="button" aria-label="Close" title="Close" class="ds-icon-btn ds-icon-btn-sm" @click="close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </div>
        <button
          v-else
          type="button"
          aria-label="Close" title="Close"
          class="ds-icon-btn ds-icon-btn-sm ds-modal-close-floating"
          @click="close"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
        </button>
        <div class="ds-modal-body"><slot /></div>
      </div>
    </div>
  </Teleport>
</template>
