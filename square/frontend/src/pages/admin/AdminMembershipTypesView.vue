<script setup lang="ts">
import { squareProfile } from '../../services/squareConfig'
import { ref, onMounted, computed, watch } from 'vue'
import MemberSectionNav from '../../components/MemberSectionNav.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseInput from '../../components/ui/BaseInput.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import FilterPills from '../../components/ui/FilterPills.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import { useClientPagination } from '../../composables/useClientPagination'
import BaseModal from '../../components/ui/BaseModal.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import {
  fetchAdminMembershipTypes,
  createAdminMembershipType,
  updateAdminMembershipType,
  ValidationError,
  type AdminMembershipType,
  type BillingFrequency,
} from '../../services/adminMembershipTypesApi'
import { formatMembershipPrice } from '../../utils/membership'
import { humanize } from '../../utils/formatEnum'
import { useToast } from '../../composables/useToast'

const toast = useToast()

const types = ref<AdminMembershipType[]>([])
const search = ref('')
const filter = ref('all')
const filterOptions = [{ value: 'all', label: 'All' }, { value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }]
const visible = computed(() => {
  const f = filter.value
  const q = search.value.trim().toLowerCase()
  return types.value.filter((m) => (f === 'all' || (f === 'active') === m.is_active) && (!q || String(m.name ?? '').toLowerCase().includes(q)))
})
const { page, totalPages, pageItems, total } = useClientPagination(visible)
watch([filter, search], () => (page.value = 1))
const loading = ref(true)

const frequencyOptions: { value: BillingFrequency; label: string }[] = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'yearly', label: 'Yearly' },
]

const modalOpen = ref(false)
const editingType = ref<AdminMembershipType | null>(null)
const saving = ref(false)
const errors = ref<Record<string, string>>({})
const form = ref({
  name: '',
  price: '0',
  billing_frequency: 'yearly' as BillingFrequency,
  contact_for_price: false,
  description: '',
  is_active: true,
  sort_order: 0,
})

async function load() {
  loading.value = true
  const { items } = await fetchAdminMembershipTypes()
  types.value = items
  loading.value = false
}

function openAdd() {
  editingType.value = null
  errors.value = {}
  form.value = {
    name: '',
    price: '0',
    billing_frequency: 'yearly',
    contact_for_price: false,
    description: '',
    is_active: true,
    sort_order: 0,
  }
  modalOpen.value = true
}

function openEdit(type: AdminMembershipType) {
  editingType.value = type
  errors.value = {}
  form.value = { ...type, price: String(type.price), description: type.description ?? '' }
  modalOpen.value = true
}

async function save() {
  saving.value = true
  errors.value = {}
  const price = parseInt(form.value.price, 10)
  try {
    if (editingType.value) {
      await updateAdminMembershipType(editingType.value.name, {
        price,
        billing_frequency: form.value.billing_frequency,
        contact_for_price: form.value.contact_for_price,
        description: form.value.description,
        is_active: form.value.is_active,
        sort_order: form.value.sort_order,
      })
      toast.success('Membership type updated')
    } else {
      await createAdminMembershipType({ ...form.value, price })
      toast.success('Membership type created')
    }
    modalOpen.value = false
    await load()
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
    } else {
      toast.error('Could not save this membership type')
    }
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-5)">
    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Memberships</h1>
      </div>
    </div>

    <MemberSectionNav />

    <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
      <h2 class="ds-display ds-display-s">Membership Types</h2>
      <BaseButton size="sm" type="button" variant="secondary" @click="openAdd">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
        Add type
      </BaseButton>
    </div>
    <p class="ds-meta" style="max-width: 720px">
      Rates and types shown here drive the public membership page, the member renewal form, and
      admin membership records — no code change needed to add a type or change a price.
    </p>

    <div class="ds-toolbar">
      <FilterPills v-model="filter" :options="filterOptions" label="Filter membership types by status" />
      <BaseSearchField size="sm" class="ds-toolbar-search" v-model="search" placeholder="Search by name…" aria-label="Search membership types" />
    </div>

    <BaseLoadingState v-if="loading" label="Loading membership types…" />
    <div v-else-if="visible.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
      <p class="ds-meta">Nothing matches this filter or search.</p>
    </div>
    <div v-else class="ds-table-wrap">
      <div class="ds-table-scroll">
        <table class="ds-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Price</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="type in pageItems" :key="type.name">
              <td data-emphasis>{{ humanize(type.name) }}</td>
              <td>{{ formatMembershipPrice(type) }}</td>
              <td><span class="ds-badge" :class="type.is_active ? 'ds-badge-success' : 'ds-badge-neutral'">{{ type.is_active ? 'Active' : 'Inactive' }}</span></td>
              <td data-align="right">
                <BaseIconButton variant="bare" size="sm" :label="`Edit ${type.name}`" @click="openEdit(type)">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                </BaseIconButton>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    <PaginationBar v-model:page="page" :total-pages="totalPages" :total="total" />
    </div>

    <BaseModal v-model="modalOpen" :title="editingType ? 'Edit membership type' : 'Add membership type'">
      <div class="space-y-4">
        <div>
          <BaseInput
            v-model="form.name"
            label="Name"
            :disabled="!!editingType"
            placeholder="e.g. individual"
          />
          <p v-if="errors.name" class="mt-1 text-sm text-error">{{ errors.name }}</p>
        </div>
        <div>
          <BaseInput v-model="form.price" type="number" :label="`Price (${squareProfile.currency})`" />
          <p v-if="errors.price" class="mt-1 text-sm text-error">{{ errors.price }}</p>
          <p class="mt-1 text-xs text-text-secondary">
            Ignored on the public page and renewal form while "Contact for pricing" is on below.
          </p>
        </div>
        <div>
          <BaseSelect
            v-model="form.billing_frequency"
            label="Billing frequency"
            :options="frequencyOptions"
          />
          <p v-if="errors.billing_frequency" class="mt-1 text-sm text-error">
            {{ errors.billing_frequency }}
          </p>
        </div>
        <BaseInput v-model="form.description" label="Description (shown to members, optional)" />
        <p v-if="errors.description" class="mt-1 text-sm text-error">{{ errors.description }}</p>
        <label class="flex items-center gap-2 text-sm text-text">
          <input v-model="form.contact_for_price" type="checkbox" />
          Contact for pricing (show "Contact us" instead of the price)
        </label>
        <label class="flex items-center gap-2 text-sm text-text">
          <input v-model="form.is_active" type="checkbox" />
          Active (selectable for new memberships)
        </label>
        <div class="flex justify-end gap-2 pt-2">
          <BaseButton variant="ghost" @click="modalOpen = false">Cancel</BaseButton>
          <BaseButton variant="primary" :disabled="saving" @click="save">
            {{ saving ? 'Saving…' : 'Save' }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>
  </div>
</template>
