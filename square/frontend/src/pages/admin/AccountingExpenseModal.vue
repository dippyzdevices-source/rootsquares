<script setup lang="ts">
import { squareProfile } from '../../services/squareConfig'
import { ref, computed, watch } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import AccountingReceiptModal from './AccountingReceiptModal.vue'
import ReceiptCameraModal from './ReceiptCameraModal.vue'
import {
  createExpense,
  updateExpense,
  uploadExpenseReceipt,
  deleteExpenseReceipt,
  ValidationError,
  type Expense,
  type ExpensePayload,
} from '../../services/adminAccountingApi'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

// Reusable Create/Edit Expense component — a single form handles both, distinguished only
// by whether `expense` is null (create) or set (edit), per the "one component, not two"
// requirement.
const props = defineProps<{ modelValue: boolean; eventId: number | null; expense: Expense | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [expense: Expense] }>()

const toast = useToast()
const { options: expenseCategories } = useLookup('expense_category')
const saving = ref(false)
const errors = ref<Record<string, string>>({})
const receiptFile = ref<File | null>(null)
const currentReceiptUrl = ref<string | null>(null)
const showReceiptViewer = ref(false)
const showCamera = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const form = ref({ date: '', description: '', category: '', amount: '', vendor: '', notes: '' })

function resetForm() {
  errors.value = {}
  receiptFile.value = null
  currentReceiptUrl.value = props.expense?.receipt_url ?? null
  if (props.expense) {
    form.value = {
      date: props.expense.date,
      description: props.expense.description,
      category: props.expense.category,
      amount: (props.expense.amount / 100).toString(),
      vendor: props.expense.vendor ?? '',
      notes: props.expense.notes ?? '',
    }
  } else {
    form.value = { date: '', description: '', category: '', amount: '', vendor: '', notes: '' }
  }
}

watch(() => props.modelValue, (open) => { if (open) resetForm() })

const isEditing = computed(() => props.expense !== null)

function buildPayload(): ExpensePayload {
  return {
    date: form.value.date,
    description: form.value.description,
    category: form.value.category,
    amount: Math.round(Number(form.value.amount) * 100),
    vendor: form.value.vendor || null,
    notes: form.value.notes || null,
  }
}

async function save() {
  if (saving.value) return // guards against an accidental double-submit
  saving.value = true
  errors.value = {}
  try {
    const payload = buildPayload()
    let saved = isEditing.value && props.expense
      ? await updateExpense(props.expense.id, payload)
      : await createExpense(props.eventId, payload)

    if (receiptFile.value) {
      try {
        saved = await uploadExpenseReceipt(saved.id, receiptFile.value)
      } catch (err) {
        if (err instanceof ValidationError) {
          errors.value = err.errors
          saving.value = false
          return // the expense itself saved fine — let the admin retry just the receipt
        }
        toast.error('Expense saved, but the receipt could not be uploaded')
      }
    }

    toast.success(isEditing.value ? 'Expense updated' : 'Expense added')
    emit('saved', saved)
    emit('update:modelValue', false)
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
    } else {
      toast.error('Could not save this expense')
    }
  } finally {
    saving.value = false
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  receiptFile.value = input.files?.[0] ?? null
}

function onPhotoCaptured(file: File) {
  receiptFile.value = file
}

function openFileBrowser() {
  fileInput.value?.click()
}

async function removeReceipt() {
  if (!props.expense) return
  try {
    const updated = await deleteExpenseReceipt(props.expense.id)
    currentReceiptUrl.value = updated.receipt_url
    emit('saved', updated)
    toast.success('Receipt removed')
  } catch {
    toast.error('Could not remove the receipt')
  }
}
</script>

<template>
  <BaseModal :model-value="modelValue" :title="isEditing ? 'Edit expense' : 'Add expense'" @update:model-value="emit('update:modelValue', $event)">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
      <label class="ds-field">
        <span class="ds-field-label">Date</span>
        <span class="ds-field-control"><input v-model="form.date" type="date" class="ds-field-input" /></span>
        <span v-if="errors.date" class="ds-field-error-text">{{ errors.date }}</span>
      </label>

      <label class="ds-field">
        <span class="ds-field-label">Description</span>
        <span class="ds-field-control"><input v-model="form.description" type="text" class="ds-field-input" /></span>
        <span v-if="errors.description" class="ds-field-error-text">{{ errors.description }}</span>
      </label>

      <BaseSelect v-model="form.category" label="Category" placeholder="Choose a category" :options="expenseCategories" />
      <span v-if="errors.category" class="ds-field-error-text">{{ errors.category }}</span>

      <label class="ds-field">
        <span class="ds-field-label">Amount ({{ squareProfile.currency }})</span>
        <span class="ds-field-control"><input v-model="form.amount" type="number" min="0" step="0.01" class="ds-field-input" /></span>
        <span v-if="errors.amount" class="ds-field-error-text">{{ errors.amount }}</span>
      </label>

      <label class="ds-field">
        <span class="ds-field-label">Vendor / payee (optional)</span>
        <span class="ds-field-control"><input v-model="form.vendor" type="text" class="ds-field-input" /></span>
        <span v-if="errors.vendor" class="ds-field-error-text">{{ errors.vendor }}</span>
      </label>

      <label class="ds-field">
        <span class="ds-field-label">Notes (optional)</span>
        <span class="ds-textarea-control">
          <textarea v-model="form.notes" rows="3" class="ds-textarea"></textarea>
        </span>
        <span v-if="errors.notes" class="ds-field-error-text">{{ errors.notes }}</span>
      </label>

      <div class="ds-field">
        <span class="ds-field-label">Receipt (optional)</span>
        <div style="display: flex; align-items: center; gap: var(--ds-space-2); flex-wrap: wrap">
          <BaseButton type="button" variant="secondary" size="sm" @click="showCamera = true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" /><circle cx="12" cy="13" r="3" /></svg>
            Take photo
          </BaseButton>
          <BaseButton type="button" variant="ghost" size="sm" @click="openFileBrowser">Choose file</BaseButton>
          <span v-if="receiptFile" class="ds-meta">{{ receiptFile.name }}</span>
        </div>
        <input
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif,application/pdf"
          style="display: none"
          @change="onFileChange"
        />
        <span v-if="errors.file" class="ds-field-error-text">{{ errors.file }}</span>
        <div v-if="currentReceiptUrl" style="margin-top: var(--ds-space-2); display: flex; align-items: center; gap: var(--ds-space-3)">
          <BaseButton type="button" variant="ghost" size="sm" @click="showReceiptViewer = true">View current receipt</BaseButton>
          <BaseButton type="button" variant="ghost" size="sm" @click="removeReceipt">Remove</BaseButton>
        </div>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" :disabled="saving" @click="emit('update:modelValue', false)">Cancel</BaseButton>
        <BaseButton type="button" class="save-expense" :disabled="saving" @click="save">
          {{ saving ? 'Saving…' : 'Save' }}
        </BaseButton>
      </div>
    </div>
  </BaseModal>

  <AccountingReceiptModal v-model="showReceiptViewer" :url="currentReceiptUrl" />
  <ReceiptCameraModal v-model="showCamera" @captured="onPhotoCaptured" />
</template>
