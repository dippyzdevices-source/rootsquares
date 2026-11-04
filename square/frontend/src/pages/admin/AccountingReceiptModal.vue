<script setup lang="ts">
import { computed } from 'vue'
import BaseModal from '../../components/ui/BaseModal.vue'

// Shared by AccountingExpenseModal (edit form) and AdminAccountingDashboardView (table row) —
// a receipt is either an image or a scanned PDF (see accounting/receipts.py's allowed types),
// so this picks the right embed based on the URL's own file extension.
const props = defineProps<{ modelValue: boolean; url: string | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const isPdf = computed(() => {
  if (!props.url) return false
  const path = props.url.split('?')[0]
  return path.toLowerCase().endsWith('.pdf')
})
</script>

<template>
  <BaseModal :model-value="modelValue" aria-label="Receipt" size="xl" @update:model-value="emit('update:modelValue', $event)">
    <div v-if="url" style="display: flex; justify-content: center">
      <iframe
        v-if="isPdf"
        :src="url"
        title="Receipt PDF"
        style="width: 100%; height: 70vh; border: none; border-radius: var(--ds-radius-md)"
      />
      <img
        v-else
        :src="url"
        alt="Receipt"
        style="max-width: 100%; max-height: 70vh; border-radius: var(--ds-radius-md)"
      />
    </div>
  </BaseModal>
</template>
