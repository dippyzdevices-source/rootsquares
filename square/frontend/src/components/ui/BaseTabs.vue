<script setup lang="ts">
defineProps<{
  modelValue: string
  tabs: { id: string; label: string }[]
}>()

defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <div>
    <div class="flex gap-1 border-b border-border" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        role="tab"
        :aria-selected="modelValue === tab.id"
        class="border-b-2 px-4 py-2 text-sm font-medium transition-colors"
        :class="
          modelValue === tab.id
            ? 'border-primary text-primary'
            : 'border-transparent text-text-secondary hover:text-text'
        "
        @click="$emit('update:modelValue', tab.id)"
      >
        {{ tab.label }}
      </button>
    </div>
    <div class="pt-4">
      <slot :name="modelValue" />
    </div>
  </div>
</template>
