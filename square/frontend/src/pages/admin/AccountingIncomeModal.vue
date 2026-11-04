<script setup lang="ts">
import { squareProfile } from '../../services/squareConfig'
import { ref, computed, watch } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import { createManualIncome, updateManualIncome, ValidationError, type GeneralIncomeRow } from '../../services/adminAccountingApi'
import { useToast } from '../../composables/useToast'

// Add or change income typed in by hand in the general book (W15-R16): a grant, a hall hire, cash at a stall. One form for both, like the expense form.
const props = defineProps<{ modelValue: boolean; income: GeneralIncomeRow | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [] }>()

const toast = useToast()
const saving = ref(false)
const errors = ref<Record<string, string>>({})
const form = ref({ date: '', description: '', amount: '', source_name: '', notes: '' })
const isEditing = computed(() => props.income !== null)

watch(() => props.modelValue, (open) => {
  if (!open) return
  errors.value = {}
  const row = props.income
  form.value = row
    ? { date: row.date, description: row.reference ?? '', amount: (row.amount / 100).toString(), source_name: row.name ?? '', notes: row.notes ?? '' }
    : { date: '', description: '', amount: '', source_name: '', notes: '' }
})

async function save() {
  if (saving.value) return
  saving.value = true
  errors.value = {}
  const payload = {
    date: form.value.date,
    description: form.value.description,
    amount: Math.round(Number(form.value.amount) * 100),
    source_name: form.value.source_name || null,
    notes: form.value.notes || null,
  }
  try {
    if (props.income?.id) await updateManualIncome(props.income.id, payload)
    else await createManualIncome(payload)
    toast.success(isEditing.value ? 'Income updated' : 'Income added')
    emit('saved')
    emit('update:modelValue', false)
  } catch (err) {
    if (err instanceof ValidationError) errors.value = err.errors
    else toast.error('Could not save this income')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <BaseModal :model-value="modelValue" :title="isEditing ? 'Edit income' : 'Add income'" @update:model-value="emit('update:modelValue', $event)">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
      <label class="ds-field">
        <span class="ds-field-label">Date</span>
        <span class="ds-field-control"><input v-model="form.date" type="date" class="ds-field-input income-date" /></span>
        <span v-if="errors.date" class="ds-field-error-text">{{ errors.date }}</span>
      </label>
      <label class="ds-field">
        <span class="ds-field-label">What was it for</span>
        <span class="ds-field-control"><input v-model="form.description" type="text" class="ds-field-input income-description" placeholder="Hall hire, grant, stall…" /></span>
        <span v-if="errors.description" class="ds-field-error-text">{{ errors.description }}</span>
      </label>
      <label class="ds-field">
        <span class="ds-field-label">Amount ({{ squareProfile.currency }})</span>
        <span class="ds-field-control"><input v-model="form.amount" type="number" min="0" step="0.01" class="ds-field-input income-amount" /></span>
        <span v-if="errors.amount" class="ds-field-error-text">{{ errors.amount }}</span>
      </label>
      <label class="ds-field">
        <span class="ds-field-label">From (optional)</span>
        <span class="ds-field-control"><input v-model="form.source_name" type="text" class="ds-field-input" /></span>
        <span v-if="errors.source_name" class="ds-field-error-text">{{ errors.source_name }}</span>
      </label>
      <label class="ds-field">
        <span class="ds-field-label">Notes (optional)</span>
        <span class="ds-textarea-control"><textarea v-model="form.notes" rows="3" class="ds-textarea"></textarea></span>
        <span v-if="errors.notes" class="ds-field-error-text">{{ errors.notes }}</span>
      </label>
      <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" :disabled="saving" @click="emit('update:modelValue', false)">Cancel</BaseButton>
        <BaseButton type="button" class="save-income" :disabled="saving" @click="save">{{ saving ? 'Saving…' : 'Save' }}</BaseButton>
      </div>
    </div>
  </BaseModal>
</template>
