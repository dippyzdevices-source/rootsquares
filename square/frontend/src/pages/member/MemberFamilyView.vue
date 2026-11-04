<script setup lang="ts">
import { ref, onMounted } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseInput from '../../components/ui/BaseInput.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'
import {
  fetchMyMember,
  createMyFamilyMember,
  updateMyFamilyMember,
  deleteMyFamilyMember,
  ValidationError,
  type FamilyMember,
} from '../../services/memberApi'

const toast = useToast()

const loading = ref(true)
const loadError = ref(false)
const familyMembers = ref<FamilyMember[]>([])

const adding = ref(false)
const editingFamilyMember = ref<FamilyMember | null>(null)
const saving = ref(false)
const formErrors = ref<Record<string, string>>({})
const form = ref({ name: '', relationship_type: '', age: '' })

const { options: relationshipOptions, label: relationshipLabel } = useLookup('relationship_type')

async function load() {
  loading.value = true
  loadError.value = false
  try {
    const profile = await fetchMyMember()
    familyMembers.value = profile.family_members ?? []
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}
onMounted(load)

function openAdd() {
  editingFamilyMember.value = null
  formErrors.value = {}
  form.value = { name: '', relationship_type: '', age: '' }
  adding.value = true
}

function openEdit(familyMember: FamilyMember) {
  editingFamilyMember.value = familyMember
  formErrors.value = {}
  form.value = {
    name: familyMember.name,
    relationship_type: familyMember.relationship_type,
    age: familyMember.age != null ? String(familyMember.age) : '',
  }
  adding.value = true
}

function cancelForm() {
  adding.value = false
  editingFamilyMember.value = null
  formErrors.value = {}
}

async function save() {
  saving.value = true
  formErrors.value = {}
  const payload = {
    name: form.value.name,
    relationship_type: form.value.relationship_type,
    age: form.value.age ? Number(form.value.age) : null,
  }
  try {
    if (editingFamilyMember.value) {
      await updateMyFamilyMember(editingFamilyMember.value.id, payload)
      toast.success('Family member updated')
    } else {
      await createMyFamilyMember(payload)
      toast.success('Family member added')
    }
    adding.value = false
    editingFamilyMember.value = null
    await load()
  } catch (err) {
    if (err instanceof ValidationError) {
      formErrors.value = err.errors
    } else {
      toast.error('Could not save this family member')
    }
  } finally {
    saving.value = false
  }
}

async function remove(familyMember: FamilyMember) {
  try {
    await deleteMyFamilyMember(familyMember.id)
    familyMembers.value = familyMembers.value.filter((f) => f.id !== familyMember.id)
    toast.success('Family member removed')
  } catch {
    toast.error('Could not remove this family member')
  }
}
</script>

<template>
  <div class="ds-scope">
    <div style="max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />My portal</span>
        <h1 class="ds-display ds-display-s">Family</h1>
      </div>

      <BaseLoadingState v-if="loading" label="Loading your family…" />
      <div v-else-if="loadError" class="ds-alert ds-alert-danger"><div>Couldn't load your family members. Please try again shortly.</div></div>

      <template v-else>
        <div class="ds-table-wrap">
          <div class="ds-table-scroll">
            <table class="ds-table">
              <caption>Household</caption>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Relation</th>
                  <th data-align="right">Age</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="familyMembers.length === 0">
                  <td colspan="4" class="ds-table-empty">No family members added yet.</td>
                </tr>
                <tr v-for="familyMember in familyMembers" :key="familyMember.id">
                  <td data-emphasis>{{ familyMember.name }}</td>
                  <td>{{ relationshipLabel(familyMember.relationship_type) }}</td>
                  <td data-align="right">{{ familyMember.age ?? '—' }}</td>
                  <td data-align="right">
                    <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                      <BaseIconButton variant="bare" size="sm" :label="`Edit ${familyMember.name}`" @click="openEdit(familyMember)">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                      </BaseIconButton>
                      <BaseIconButton variant="danger" size="sm" :label="`Remove ${familyMember.name}`" @click="remove(familyMember)">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /><line x1="10" x2="10" y1="11" y2="17" /><line x1="14" x2="14" y1="11" y2="17" /></svg>
                      </BaseIconButton>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-if="adding" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
          <h2 class="ds-title">{{ editingFamilyMember ? 'Edit family member' : 'Add someone to the household' }}</h2>
          <div style="display: grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr); gap: var(--ds-space-4)">
            <div>
              <BaseInput v-model="form.name" label="Name" placeholder="Full name" />
              <p v-if="formErrors.name" class="ds-field-error-text">{{ formErrors.name }}</p>
            </div>
            <div>
              <BaseSelect v-model="form.relationship_type" label="Relation" placeholder="Choose a relationship" :options="relationshipOptions" />
              <p v-if="formErrors.relationship_type" class="ds-field-error-text">{{ formErrors.relationship_type }}</p>
            </div>
          </div>
          <div>
            <BaseInput v-model="form.age" type="number" label="Age (optional)" />
            <p v-if="formErrors.age" class="ds-field-error-text">{{ formErrors.age }}</p>
          </div>
          <div style="display: flex; gap: var(--ds-space-3)">
            <BaseButton type="button" class="save-family-member" :disabled="saving" @click="save">
              {{ saving ? 'Saving…' : (editingFamilyMember ? 'Save changes' : 'Add person') }}
            </BaseButton>
            <BaseButton type="button" variant="ghost" @click="cancelForm">Cancel</BaseButton>
          </div>
        </div>
        <BaseButton v-else type="button" variant="secondary" class="add-family-member" style="align-self: flex-start" @click="openAdd">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><line x1="19" y1="8" x2="19" y2="14" /><line x1="22" y1="11" x2="16" y2="11" /></svg>
          Add a person
        </BaseButton>
      </template>
    </div>
  </div>
</template>
