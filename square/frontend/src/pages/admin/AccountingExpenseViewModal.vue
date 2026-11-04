<script setup lang="ts">
import { computed, ref } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import AccountingReceiptModal from './AccountingReceiptModal.vue'
import type { Expense } from '../../services/adminAccountingApi'
import { useLookup } from '../../composables/useLookup'
import { formatPrice } from '../../utils/money'
import { formatEventDate } from '../../utils/date'

// Read-only companion to AccountingExpenseModal — lets an admin glance at every field
// (notably `notes`, which the expenses table has no column for) without entering edit mode.
const props = defineProps<{ modelValue: boolean; expense: Expense | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; edit: [expense: Expense] }>()

const showReceiptViewer = ref(false)

const { label: expenseCategoryLabel } = useLookup('expense_category')
const categoryLabel = computed(() => (props.expense ? expenseCategoryLabel(props.expense.category) : ''))

function editFromView() {
  if (!props.expense) return
  emit('edit', props.expense)
}
</script>

<template>
  <BaseModal :model-value="modelValue" title="Expense details" @update:model-value="emit('update:modelValue', $event)">
    <div v-if="expense" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
      <div>
        <span class="ds-field-label">Date</span>
        <div class="ds-field-readonly">{{ formatEventDate(expense.date) }}</div>
      </div>
      <div>
        <span class="ds-field-label">Description</span>
        <div class="ds-field-readonly">{{ expense.description }}</div>
      </div>
      <div>
        <span class="ds-field-label">Category</span>
        <div class="ds-field-readonly"><span class="ds-badge ds-badge-neutral">{{ categoryLabel }}</span></div>
      </div>
      <div>
        <span class="ds-field-label">Amount</span>
        <div class="ds-field-readonly">{{ formatPrice(expense.amount) }}</div>
      </div>
      <div>
        <span class="ds-field-label">Vendor / payee</span>
        <div class="ds-field-readonly">{{ expense.vendor ?? '—' }}</div>
      </div>
      <div>
        <span class="ds-field-label">Notes</span>
        <div class="ds-field-readonly" style="white-space: pre-wrap; align-items: flex-start">{{ expense.notes ?? '—' }}</div>
      </div>
      <div>
        <span class="ds-field-label">Receipt</span>
        <div class="ds-field-readonly">
          <BaseButton v-if="expense.receipt_url" type="button" variant="ghost" size="sm" @click="showReceiptViewer = true">
            View receipt
          </BaseButton>
          <template v-else>—</template>
        </div>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="emit('update:modelValue', false)">Close</BaseButton>
        <BaseButton type="button" @click="editFromView">Edit</BaseButton>
      </div>
    </div>
  </BaseModal>

  <AccountingReceiptModal v-model="showReceiptViewer" :url="expense?.receipt_url ?? null" />
</template>
