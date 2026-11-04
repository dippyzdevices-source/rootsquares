<script setup lang="ts">
import { squareProfile } from '../../services/squareConfig'
import { ref, computed, watch } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import {
  createContribution,
  updateContribution,
  ValidationError,
  type Contribution,
  type ContributionPayload,
} from '../../services/adminAccountingApi'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

// One form for add and edit (edit when `contribution` is set), like the expense modal.
const props = defineProps<{ modelValue: boolean; eventId: number; contribution: Contribution | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [contribution: Contribution] }>()

const toast = useToast()
const { options: providerOptions } = useLookup('payment_provider')
const saving = ref(false)
const errors = ref<Record<string, string>>({})

const KIND_OPTIONS = [
  { value: 'donation', label: 'Donation' },
  { value: 'sponsorship', label: 'Sponsorship' },
]
const methodOptions = computed(() => [{ value: '', label: 'Not specified' }, ...providerOptions.value])

const STATUS_OPTIONS = [
  { value: 'pending', label: 'Pending (not received yet)' },
  { value: 'paid', label: 'Received' },
]

const empty = () => ({
  kind: 'donation',
  name: '',
  email: '',
  amount: '',
  date: '',
  payment_method: '',
  notes: '',
  status: 'paid',
  contact_name: '',
  phone: '',
  website: '',
  requirements: '',
})
const form = ref(empty())

function resetForm() {
  errors.value = {}
  const c = props.contribution
  form.value = c
    ? {
        kind: c.kind,
        name: c.name,
        email: c.email ?? '',
        amount: c.amount != null ? (c.amount / 100).toString() : '',
        date: c.date,
        payment_method: c.payment_method ?? '',
        notes: c.notes ?? '',
        status: c.status === 'paid' ? 'paid' : 'pending',
        contact_name: c.contact_name ?? '',
        phone: c.phone ?? '',
        website: c.website ?? '',
        requirements: c.requirements ?? '',
      }
    : empty()
}
watch(() => props.modelValue, (open) => { if (open) resetForm() })

const isEditing = computed(() => props.contribution !== null)
const nameLabel = computed(() => (form.value.kind === 'sponsorship' ? 'Sponsor' : 'Donor (leave blank for anonymous)'))

async function save() {
  if (saving.value) return
  saving.value = true
  errors.value = {}
  const payload: ContributionPayload = {
    kind: form.value.kind as ContributionPayload['kind'],
    name: form.value.name,
    email: form.value.email || null,
    amount: form.value.amount ? Math.round(Number(form.value.amount) * 100) : undefined,
    date: form.value.date,
    payment_method: form.value.payment_method || null,
    notes: form.value.notes || null,
    status: form.value.status as ContributionPayload['status'],
    ...(form.value.kind === 'sponsorship'
      ? {
          contact_name: form.value.contact_name || null,
          phone: form.value.phone || null,
          website: form.value.website || null,
          requirements: form.value.requirements || null,
        }
      : {}),
  }
  try {
    const saved = props.contribution
      ? await updateContribution(props.contribution.id, payload)
      : await createContribution(props.eventId, payload)
    toast.success(isEditing.value ? 'Updated' : 'Added')
    emit('saved', saved)
    emit('update:modelValue', false)
  } catch (err) {
    if (err instanceof ValidationError) errors.value = err.errors
    else toast.error('Could not save this entry')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    :title="isEditing ? 'Edit donation / sponsorship' : 'Add donation / sponsorship'"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
      <BaseSelect v-model="form.kind" label="Type" :options="KIND_OPTIONS" />
      <span v-if="errors.kind" class="ds-field-error-text">{{ errors.kind }}</span>

      <label class="ds-field">
        <span class="ds-field-label">{{ nameLabel }}</span>
        <span class="ds-field-control"><input v-model="form.name" type="text" class="ds-field-input" /></span>
        <span v-if="errors.name" class="ds-field-error-text">{{ errors.name }}</span>
      </label>

      <label class="ds-field">
        <span class="ds-field-label">Email (optional)</span>
        <span class="ds-field-control"><input v-model="form.email" type="email" class="ds-field-input" /></span>
        <span v-if="errors.email" class="ds-field-error-text">{{ errors.email }}</span>
      </label>

      <label class="ds-field">
        <span class="ds-field-label">Amount ({{ squareProfile.currency }})</span>
        <span class="ds-field-control"><input v-model="form.amount" type="number" min="0" step="0.01" class="ds-field-input" /></span>
        <span v-if="errors.amount" class="ds-field-error-text">{{ errors.amount }}</span>
      </label>

      <label class="ds-field">
        <span class="ds-field-label">Date received</span>
        <span class="ds-field-control"><input v-model="form.date" type="date" class="ds-field-input" /></span>
        <span v-if="errors.date" class="ds-field-error-text">{{ errors.date }}</span>
      </label>

      <BaseSelect v-model="form.payment_method" label="Received by (optional)" :options="methodOptions" />

      <BaseSelect v-model="form.status" label="Status" :options="STATUS_OPTIONS" />
      <span v-if="errors.status" class="ds-field-error-text">{{ errors.status }}</span>

      <template v-if="form.kind === 'sponsorship'">
        <label class="ds-field">
          <span class="ds-field-label">Contact person (optional)</span>
          <span class="ds-field-control"><input v-model="form.contact_name" type="text" class="ds-field-input" /></span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Phone (optional)</span>
          <span class="ds-field-control"><input v-model="form.phone" type="tel" class="ds-field-input" /></span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Website (optional)</span>
          <span class="ds-field-control"><input v-model="form.website" type="url" class="ds-field-input" /></span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Sponsor's requirements (optional)</span>
          <span class="ds-textarea-control"><textarea v-model="form.requirements" rows="3" class="ds-textarea"></textarea></span>
          <span v-if="errors.requirements" class="ds-field-error-text">{{ errors.requirements }}</span>
        </label>
      </template>

      <label class="ds-field">
        <span class="ds-field-label">Notes (optional)</span>
        <span class="ds-textarea-control"><textarea v-model="form.notes" rows="3" class="ds-textarea"></textarea></span>
        <span v-if="errors.notes" class="ds-field-error-text">{{ errors.notes }}</span>
      </label>

      <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" :disabled="saving" @click="emit('update:modelValue', false)">Cancel</BaseButton>
        <BaseButton type="button" class="save-contribution" :disabled="saving" @click="save">{{ saving ? 'Saving…' : 'Save' }}</BaseButton>
      </div>
    </div>
  </BaseModal>
</template>
