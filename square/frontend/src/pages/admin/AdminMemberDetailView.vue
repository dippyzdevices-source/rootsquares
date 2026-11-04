<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import BaseAvatar from '../../components/ui/BaseAvatar.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import {
  fetchAdminMember,
  exportMemberPersonalData,
  setAdminMemberErase,
  updateAdminMember,
  createAdminFamilyMember,
  updateAdminFamilyMember,
  deleteAdminFamilyMember,
  ValidationError as FamilyMemberValidationError,
  type AdminMemberDetail,
} from '../../services/adminMembersApi'
import {
  createAdminMembership,
  updateAdminMembership,
  ValidationError,
  type MembershipPayload,
} from '../../services/adminMembershipsApi'
import { fetchAdminMembershipTypes } from '../../services/adminMembershipTypesApi'
import type { MembershipRecord, FamilyMember } from '../../services/memberApi'
import { downloadBlob } from '../../utils/download'
import { formatEventDate } from '../../utils/date'
import { formatMembershipPrice } from '../../utils/membership'
import { moduleEnabled } from '../../services/modules'
import { humanize } from '../../utils/formatEnum'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const { label: membershipStatusLabel } = useLookup('membership_status')
// Without the Memberships module (ADR 044) the member page is a person's page: profile and family, no membership history.
const membershipsOn = moduleEnabled('memberships')
const noun = membershipsOn ? 'Members' : 'People'
const route = useRoute()
const toast = useToast()

const memberId = computed(() => Number(route.params.id))

const loading = ref(true)
const loadError = ref(false)
const member = ref<AdminMemberDetail | null>(null)

const exportingData = ref(false)
async function exportPersonalData() {
  exportingData.value = true
  try {
    downloadBlob(await exportMemberPersonalData(memberId.value), `personal-data-${memberId.value}.json`)
  } catch {
    toast.error('Could not export the personal data')
  } finally {
    exportingData.value = false
  }
}

const eraseModalOpen = ref(false)
const savingErase = ref(false)
const eraseDueDate = computed(() => {
  const at = member.value?.erase_requested_at
  return at ? formatEventDate(new Date(new Date(at).getTime() + 30 * 86400000).toISOString()) : ''
})
async function changeErase(action: 'erase-request' | 'erase-cancel') {
  savingErase.value = true
  try {
    member.value = await setAdminMemberErase(memberId.value, action)
    eraseModalOpen.value = false
  } catch {
    toast.error('Could not update the erase request')
  } finally {
    savingErase.value = false
  }
}

const editingProfile = ref(false)
const savingProfile = ref(false)
const profileForm = ref({ name: '', address: '', parentEmail: '' })

const familyModalOpen = ref(false)
const editingFamilyMember = ref<FamilyMember | null>(null)
const savingFamilyMember = ref(false)
const familyErrors = ref<Record<string, string>>({})
const familyForm = ref({ name: '', relationship_type: '', age: '' })

const { options: relationshipOptions, label: relationshipLabel } = useLookup('relationship_type')

const membershipModalOpen = ref(false)
const editingMembership = ref<MembershipRecord | null>(null)
const savingMembership = ref(false)
const membershipErrors = ref<Record<string, string>>({})
const membershipForm = ref({
  membership_type: '',
  status: 'pending',
  start_date: '',
  end_date: '',
})

const typeOptions = ref<{ value: string; label: string }[]>([])
const statusOptions = computed(() => [
  { value: 'pending', label: membershipStatusLabel('pending') },
  { value: 'active', label: membershipStatusLabel('active') },
  { value: 'expired', label: membershipStatusLabel('expired') },
  { value: 'cancelled', label: membershipStatusLabel('cancelled') },
  { value: 'suspended', label: membershipStatusLabel('suspended') },
])

const profileRows = computed(() => [
  { label: 'Email', value: member.value?.email || '—' },
  { label: 'Phone', value: member.value?.phone || '—' },
  { label: 'Address', value: member.value?.address || '—' },
])

function membershipTone(status: string): string {
  if (status === 'active') return 'ds-badge-success'
  if (status === 'expired' || status === 'cancelled' || status === 'suspended') return 'ds-badge-danger'
  return 'ds-badge-neutral'
}

async function load() {
  loading.value = true
  loadError.value = false
  try {
    member.value = await fetchAdminMember(memberId.value)
    profileForm.value = {
      name: member.value.name,
      address: member.value.address ?? '',
      parentEmail: member.value.parent?.email ?? '',
    }
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }

  if (!membershipsOn) return
  try {
    const { items } = await fetchAdminMembershipTypes()
    typeOptions.value = items.map((t) => ({
      value: t.name,
      label: `${humanize(t.name)} (${formatMembershipPrice(t)})${t.is_active ? '' : ' — inactive'}`,
    }))
  } catch {
    // Membership-type options are secondary — the profile/history load error already surfaced.
  }
}

async function saveProfile() {
  savingProfile.value = true
  try {
    member.value = await updateAdminMember(memberId.value, {
      name: profileForm.value.name,
      address: profileForm.value.address || null,
      // Only sent when changed; blank clears the parent link.
      ...(profileForm.value.parentEmail.trim() !== (member.value?.parent?.email ?? '')
        ? { parent_email: profileForm.value.parentEmail.trim() || null }
        : {}),
    })
    editingProfile.value = false
    toast.success('Profile updated')
  } catch {
    toast.error('Could not save this profile')
  } finally {
    savingProfile.value = false
  }
}

function openAddFamilyMember() {
  editingFamilyMember.value = null
  familyErrors.value = {}
  familyForm.value = { name: '', relationship_type: '', age: '' }
  familyModalOpen.value = true
}

function openEditFamilyMember(familyMember: FamilyMember) {
  editingFamilyMember.value = familyMember
  familyErrors.value = {}
  familyForm.value = {
    name: familyMember.name,
    relationship_type: familyMember.relationship_type,
    age: familyMember.age != null ? String(familyMember.age) : '',
  }
  familyModalOpen.value = true
}

async function saveFamilyMember() {
  savingFamilyMember.value = true
  familyErrors.value = {}
  const payload = {
    name: familyForm.value.name,
    relationship_type: familyForm.value.relationship_type,
    age: familyForm.value.age ? Number(familyForm.value.age) : null,
  }
  try {
    if (editingFamilyMember.value) {
      await updateAdminFamilyMember(memberId.value, editingFamilyMember.value.id, payload)
      toast.success('Family member updated')
    } else {
      await createAdminFamilyMember(memberId.value, payload)
      toast.success('Family member added')
    }
    familyModalOpen.value = false
    await load()
  } catch (err) {
    if (err instanceof FamilyMemberValidationError) {
      familyErrors.value = err.errors
    } else {
      toast.error('Could not save this family member')
    }
  } finally {
    savingFamilyMember.value = false
  }
}

async function removeFamilyMember(familyMember: FamilyMember) {
  try {
    await deleteAdminFamilyMember(memberId.value, familyMember.id)
    toast.success('Family member removed')
    await load()
  } catch {
    toast.error('Could not remove this family member')
  }
}

function openAddMembership() {
  editingMembership.value = null
  membershipErrors.value = {}
  membershipForm.value = { membership_type: '', status: 'pending', start_date: '', end_date: '' }
  membershipModalOpen.value = true
}

function openEditMembership(membership: MembershipRecord) {
  editingMembership.value = membership
  membershipErrors.value = {}
  membershipForm.value = {
    membership_type: membership.membership_type,
    status: membership.status,
    start_date: membership.start_date,
    end_date: membership.end_date ?? '',
  }
  membershipModalOpen.value = true
}

async function saveMembership() {
  savingMembership.value = true
  membershipErrors.value = {}
  const payload: MembershipPayload = {
    membership_type: membershipForm.value.membership_type,
    status: membershipForm.value.status,
    start_date: membershipForm.value.start_date,
    end_date: membershipForm.value.end_date || null,
  }
  try {
    if (editingMembership.value) {
      await updateAdminMembership(editingMembership.value.id, payload)
      toast.success('Membership updated')
    } else {
      await createAdminMembership({ ...payload, member_id: memberId.value })
      toast.success('Membership created')
    }
    membershipModalOpen.value = false
    await load()
  } catch (err) {
    if (err instanceof ValidationError) {
      membershipErrors.value = err.errors
    } else {
      toast.error('Could not save this membership')
    }
  } finally {
    savingMembership.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <BaseLoadingState v-if="loading" label="Loading member…" />
    <div v-else-if="loadError" class="ds-alert ds-alert-danger"><div>Could not load this member.</div></div>

    <template v-else-if="member">
      <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
          <h1 class="ds-display ds-display-s">{{ noun }}</h1>
        </div>
        <BaseButton type="button" to="/admin/members" variant="secondary" size="sm">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
          Back
        </BaseButton>
      </div>

      <hr class="ds-section-line" />

      <section class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-5)">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
          <div style="display: flex; align-items: center; gap: var(--ds-space-4); min-width: 0">
            <BaseAvatar :src="member.photo_url" :name="member.name" size="xl" />
            <div style="min-width: 0; display: flex; flex-direction: column; gap: var(--ds-space-2)">
              <h2 class="ds-display ds-display-s" style="overflow-wrap: anywhere">{{ member.name }}</h2>
              <span v-if="member.memberships[0]" class="ds-badge" :class="membershipTone(member.memberships[0].status)" style="align-self: flex-start">
                {{ humanize(member.memberships[0].membership_type) }} · {{ membershipStatusLabel(member.memberships[0].status) }}
              </span>
            </div>
          </div>
          <div v-if="!editingProfile" style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap">
            <BaseButton type="button" variant="secondary" size="sm" :disabled="exportingData" @click="exportPersonalData">Export personal data</BaseButton>
            <BaseButton type="button" variant="secondary" size="sm" @click="editingProfile = true">Edit profile</BaseButton>
          </div>
        </div>

        <div v-if="editingProfile" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
          <label class="ds-field">
            <span class="ds-field-label">Full name</span>
            <span class="ds-field-control"><input v-model="profileForm.name" type="text" class="ds-field-input" /></span>
          </label>
          <label class="ds-field">
            <span class="ds-field-label">Address</span>
            <span class="ds-field-control"><input v-model="profileForm.address" type="text" class="ds-field-input" /></span>
          </label>
          <label class="ds-field">
            <span class="ds-field-label">Parent's email (children only)</span>
            <span class="ds-field-control"><input v-model="profileForm.parentEmail" type="email" class="ds-field-input" /></span>
          </label>
          <div style="display: flex; gap: var(--ds-space-2)">
            <BaseButton type="button" variant="primary" size="md" :disabled="savingProfile" @click="saveProfile">
              {{ savingProfile ? 'Saving…' : 'Save' }}
            </BaseButton>
            <BaseButton type="button" variant="ghost" size="md" @click="editingProfile = false">Cancel</BaseButton>
          </div>
        </div>
        <div v-else class="ds-deflist">
          <template v-for="row in profileRows" :key="row.label">
            <p class="ds-eyebrow" style="align-self: center">{{ row.label }}</p>
            <p class="ds-body" style="align-self: center; overflow-wrap: anywhere">{{ row.value }}</p>
          </template>
        </div>
      </section>

      <section v-if="membershipsOn" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4)">
          <h2 class="ds-title">Family</h2>
          <BaseButton type="button" variant="secondary" size="sm" class="add-family-member" @click="openAddFamilyMember">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
            Add family member
          </BaseButton>
        </div>
        <div class="ds-table-wrap">
          <div class="ds-table-scroll">
            <table class="ds-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Relation</th>
                  <th data-align="right">Age</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="member.family_members.length === 0">
                  <td colspan="4" class="ds-table-empty">No family members added yet.</td>
                </tr>
                <tr v-for="familyMember in member.family_members" :key="familyMember.id">
                  <td data-emphasis>{{ familyMember.name }}</td>
                  <td>{{ relationshipLabel(familyMember.relationship_type) }}</td>
                  <td data-align="right">{{ familyMember.age ?? '—' }}</td>
                  <td data-align="right">
                    <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                      <BaseIconButton variant="bare" size="sm" :label="`Edit ${familyMember.name}`" @click="openEditFamilyMember(familyMember)">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                      </BaseIconButton>
                      <BaseIconButton variant="danger" size="sm" :label="`Remove ${familyMember.name}`" @click="removeFamilyMember(familyMember)">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /><line x1="10" x2="10" y1="11" y2="17" /><line x1="14" x2="14" y1="11" y2="17" /></svg>
                      </BaseIconButton>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section v-if="membershipsOn" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4)">
          <h2 class="ds-title">Membership history</h2>
          <BaseButton type="button" variant="secondary" size="sm" @click="openAddMembership">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
            Add membership
          </BaseButton>
        </div>

        <div v-if="member.memberships.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
          <p class="ds-meta">No membership records yet.</p>
        </div>
        <div v-else class="ds-table-wrap">
          <div class="ds-table-scroll">
            <table class="ds-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Start</th>
                  <th>End</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="membership in member.memberships" :key="membership.id">
                  <td data-emphasis>{{ humanize(membership.membership_type) }}</td>
                  <td><span class="ds-badge" :class="membershipTone(membership.status)">{{ membershipStatusLabel(membership.status) }}</span></td>
                  <td>{{ formatEventDate(membership.start_date) }}</td>
                  <td>{{ membership.end_date ? formatEventDate(membership.end_date) : '—' }}</td>
                  <td data-align="right">
                    <BaseIconButton variant="bare" size="sm" :label="`Edit ${humanize(membership.membership_type)} membership`" @click="openEditMembership(membership)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                    </BaseIconButton>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <h2 class="ds-title">Erase this person</h2>
        <p v-if="member.erased_at" class="ds-body">Erased on {{ formatEventDate(member.erased_at) }}. Names, contact details and photo are removed; counts and amounts are kept.</p>
        <template v-else-if="member.erase_requested_at">
          <p class="ds-body">Erase requested. Sign-in is blocked now; the personal data is anonymised on {{ eraseDueDate }}.</p>
          <div><BaseButton type="button" variant="secondary" size="sm" :disabled="savingErase" @click="changeErase('erase-cancel')">Cancel the request</BaseButton></div>
        </template>
        <template v-else>
          <p class="ds-body">When the person asks to be forgotten. Their orders and payments stay as anonymous records.</p>
          <div><BaseButton type="button" variant="danger" size="sm" @click="eraseModalOpen = true">Erase this person…</BaseButton></div>
        </template>
      </section>
    </template>

    <BaseModal v-model="eraseModalOpen" title="Erase this person?">
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <p class="ds-body">Sign-in stops now. After 30 days the name, e-mail, phone, address, photo and family details are anonymised, including their orders and newsletter entry. Nothing is deleted from the counts or accounts. You can cancel during the 30 days.</p>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" @click="eraseModalOpen = false">Cancel</BaseButton>
          <BaseButton type="button" variant="danger" :disabled="savingErase" @click="changeErase('erase-request')">Erase after 30 days</BaseButton>
        </div>
      </div>
    </BaseModal>

    <BaseModal
      v-if="membershipsOn"
      v-model="membershipModalOpen"
      :title="editingMembership ? 'Edit membership' : 'Add membership'"
    >
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <label class="ds-field">
          <span class="ds-field-label">Type</span>
          <BaseSelect v-model="membershipForm.membership_type" :options="typeOptions" placeholder="Choose a type" />
          <span v-if="membershipErrors.membership_type" class="ds-field-error-text">{{ membershipErrors.membership_type }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Status</span>
          <BaseSelect v-model="membershipForm.status" :options="statusOptions" />
          <span v-if="membershipErrors.status" class="ds-field-error-text">{{ membershipErrors.status }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Start date</span>
          <span class="ds-field-control"><input v-model="membershipForm.start_date" type="date" class="ds-field-input" /></span>
          <span v-if="membershipErrors.start_date" class="ds-field-error-text">{{ membershipErrors.start_date }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">End date (optional)</span>
          <span class="ds-field-control"><input v-model="membershipForm.end_date" type="date" class="ds-field-input" /></span>
          <span v-if="membershipErrors.end_date" class="ds-field-error-text">{{ membershipErrors.end_date }}</span>
        </label>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" size="md" @click="membershipModalOpen = false">Cancel</BaseButton>
          <BaseButton type="button" variant="primary" size="md" :disabled="savingMembership" @click="saveMembership">
            {{ savingMembership ? 'Saving…' : 'Save' }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>

    <BaseModal
      v-model="familyModalOpen"
      :title="editingFamilyMember ? 'Edit family member' : 'Add family member'"
    >
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <label class="ds-field">
          <span class="ds-field-label">Name</span>
          <span class="ds-field-control"><input v-model="familyForm.name" type="text" class="ds-field-input" /></span>
          <span v-if="familyErrors.name" class="ds-field-error-text">{{ familyErrors.name }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Relationship</span>
          <BaseSelect v-model="familyForm.relationship_type" :options="relationshipOptions" placeholder="Choose a relationship" />
          <span v-if="familyErrors.relationship_type" class="ds-field-error-text">{{ familyErrors.relationship_type }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Age (optional)</span>
          <span class="ds-field-control"><input v-model="familyForm.age" type="number" class="ds-field-input" /></span>
          <span v-if="familyErrors.age" class="ds-field-error-text">{{ familyErrors.age }}</span>
        </label>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" @click="familyModalOpen = false">Cancel</BaseButton>
          <BaseButton
            type="button"
            class="save-family-member"
            :disabled="savingFamilyMember"
            @click="saveFamilyMember"
          >
            {{ savingFamilyMember ? 'Saving…' : 'Save' }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>
  </div>
</template>
