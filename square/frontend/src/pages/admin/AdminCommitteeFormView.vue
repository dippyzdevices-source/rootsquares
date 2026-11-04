<script setup lang="ts">
import { phonePrefix } from '../../utils/phone'
import SettingsSectionNav from '../../components/SettingsSectionNav.vue'
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AvatarCropModal from '../../components/ui/AvatarCropModal.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import {
  fetchAdminCommitteeMember,
  createAdminCommitteeMember,
  updateAdminCommitteeMember,
  uploadAdminCommitteePhoto,
  ValidationError,
  type AdminCommitteeMember,
  type CommitteeMemberPayload,
} from '../../services/adminCommitteeApi'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

// A role loaded from the API (or typed by hand) that isn't one of the preset options is
// treated as "Other" in the dropdown, revealing a free-text field pre-filled with it.
const OTHER_ROLE = '__other__'

const route = useRoute()
const toast = useToast()

// Id of a record created on this page. The URL is swapped to /edit with history.replaceState, which
// does not change route.params, so without this a second Save would create a duplicate.
const createdId = ref<number | null>(null)
const memberId = computed(() => {
  const id = route.params.id
  return id ? Number(id) : createdId.value
})
const isEditing = computed(() => memberId.value !== null)

const loading = ref(isEditing.value)
const saving = ref(false)
const uploading = ref(false)
const errors = ref<Record<string, string>>({})
const member = ref<AdminCommitteeMember | null>(null)
const cropModalOpen = ref(false)
const pendingPhotoFile = ref<File | null>(null)
// Matches the public committee card's own portrait aspect ratio (design-system.css's
// .ds-portrait-thumb) and this form's own preview box below — a tall rectangle, not a square.
const PORTRAIT_ASPECT_RATIO = 3 / 4

const form = ref({
  name: '',
  sub_name: '',
  role: '',
  address: '',
  email: '',
  phone: '',
  member_since: '',
  quote: '',
  display_order: '0',
  is_active: true,
})
const roleSelection = ref('')
// Positions come from the admin-managed "committee_role" list; the stored role is the label text,
// not enforced server-side — "Other" reveals a free-text field for a role outside the list.
const { options: roleLookup } = useLookup('committee_role')
const roleOptions = computed(() => roleLookup.value.map((o) => ({ value: o.label, label: o.label })))

function applyRole(role: string) {
  form.value.role = role
  roleSelection.value = roleOptions.value.some((o) => o.value === role) ? role : OTHER_ROLE
}

function onRoleSelectionChange() {
  if (roleSelection.value !== OTHER_ROLE) form.value.role = roleSelection.value
}

async function loadMember() {
  if (memberId.value === null) return
  try {
    member.value = await fetchAdminCommitteeMember(memberId.value)
    form.value = {
      name: member.value.name,
      sub_name: member.value.sub_name ?? '',
      role: member.value.role,
      address: member.value.address ?? '',
      email: member.value.email ?? '',
      phone: member.value.phone ?? '',
      member_since: member.value.member_since ? String(member.value.member_since) : '',
      quote: member.value.quote ?? '',
      display_order: String(member.value.display_order),
      is_active: member.value.is_active,
    }
    applyRole(member.value.role)
  } catch {
    toast.error('Could not load this committee member')
  } finally {
    loading.value = false
  }
}

onMounted(loadMember)

function buildPayload(): CommitteeMemberPayload {
  return {
    name: form.value.name,
    sub_name: form.value.sub_name || null,
    role: form.value.role,
    address: form.value.address || null,
    email: form.value.email || null,
    phone: form.value.phone || null,
    member_since: form.value.member_since ? Number(form.value.member_since) : null,
    quote: form.value.quote || null,
    display_order: Number(form.value.display_order) || 0,
    is_active: form.value.is_active,
  }
}

async function save() {
  saving.value = true
  errors.value = {}
  try {
    if (isEditing.value && memberId.value !== null) {
      member.value = await updateAdminCommitteeMember(memberId.value, buildPayload())
      toast.success('Committee member updated')
    } else {
      member.value = await createAdminCommitteeMember(buildPayload())
      createdId.value = member.value.id
      toast.success('Committee member created — you can now upload a portrait')
      history.replaceState(null, '', `/admin/content/committee/${member.value.id}/edit`)
    }
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
    } else {
      toast.error('Could not save this committee member')
    }
  } finally {
    saving.value = false
  }
}

function onPhotoSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  pendingPhotoFile.value = file
  cropModalOpen.value = true
  input.value = ''
}

async function onPhotoCropped(blob: Blob) {
  cropModalOpen.value = false
  if (!member.value) return
  const file = new File([blob], 'portrait.jpg', { type: 'image/jpeg' })

  uploading.value = true
  try {
    member.value = await uploadAdminCommitteePhoto(member.value.id, file)
    toast.success('Portrait uploaded')
  } catch {
    toast.error('Could not upload this portrait')
  } finally {
    uploading.value = false
    pendingPhotoFile.value = null
  }
}
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Settings</h1>
        <p class="ds-intro">Site-wide settings and content that do not change often.</p>
      </div>
      <BaseButton type="button" to="/admin/content/committee" variant="secondary" size="sm">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
        Back
      </BaseButton>
    </div>

    <SettingsSectionNav />

    <div style="max-width: 640px; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <h2 class="ds-display ds-display-s">{{ isEditing ? 'Edit committee member' : 'New committee member' }}</h2>

      <BaseLoadingState v-if="loading" label="Loading committee member…" />
      <template v-else>
        <div v-if="member" class="ds-card" style="display: flex; align-items: center; gap: var(--ds-space-4)">
        <div class="ds-arch" style="aspect-ratio: 3 / 4; width: 96px; flex-shrink: 0">
          <img v-if="member.portrait_url" :src="member.portrait_url" :alt="member.name" class="ds-arch-inner" style="object-fit: cover" />
          <div v-else class="ds-arch-inner ds-placeholder"><span class="ds-placeholder-glyph">✺</span></div>
        </div>
        <div>
          <label class="ds-field-label" style="cursor: pointer">
            {{ uploading ? 'Uploading…' : 'Upload portrait' }}
            <input type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" style="display: none" :disabled="uploading" @change="onPhotoSelected" />
          </label>
          <p class="ds-caption" style="margin-top: 4px">JPEG, PNG, or WebP.</p>
        </div>
      </div>

      <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <label class="ds-field">
          <span class="ds-field-label">Name</span>
          <span class="ds-field-control"><input v-model="form.name" type="text" placeholder="Priya Das" class="ds-field-input" /></span>
          <span v-if="errors.name" class="ds-field-error-text">{{ errors.name }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Sub-name (optional)</span>
          <span class="ds-field-control"><input v-model="form.sub_name" type="text" placeholder="Name in your own language" class="ds-field-input" /></span>
          <span class="ds-field-hint">Shown in muted text under the name — e.g. a translation.</span>
          <span v-if="errors.sub_name" class="ds-field-error-text">{{ errors.sub_name }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Role / position</span>
          <BaseSelect v-model="roleSelection" :options="[...roleOptions, { value: OTHER_ROLE, label: 'Other' }]" placeholder="Choose a role" @change="onRoleSelectionChange" />
          <span v-if="roleSelection === OTHER_ROLE" class="ds-field-control" style="margin-top: var(--ds-space-2)">
            <input v-model="form.role" type="text" placeholder="Enter the exact role" class="ds-field-input" />
          </span>
          <span v-if="errors.role" class="ds-field-error-text">{{ errors.role }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Address (optional)</span>
          <span class="ds-field-control"><input v-model="form.address" type="text" class="ds-field-input" /></span>
          <span class="ds-field-hint">Shown publicly on the committee page — only include what should be public.</span>
          <span v-if="errors.address" class="ds-field-error-text">{{ errors.address }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Email (optional)</span>
          <span class="ds-field-control"><input v-model="form.email" type="email" placeholder="name@yourclub.org" class="ds-field-input" /></span>
          <span class="ds-field-hint">Shown publicly as a mailto: link.</span>
          <span v-if="errors.email" class="ds-field-error-text">{{ errors.email }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Phone (optional)</span>
          <span class="ds-field-control"><input v-model="form.phone" type="text" :placeholder="`${phonePrefix()}…`" class="ds-field-input" /></span>
          <span class="ds-field-hint">Shown publicly as a tel: link.</span>
          <span v-if="errors.phone" class="ds-field-error-text">{{ errors.phone }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Member since (optional)</span>
          <span class="ds-field-control"><input v-model="form.member_since" type="number" placeholder="1994" class="ds-field-input" /></span>
          <span class="ds-field-hint">The year they joined — shown publicly as "Member since &lt;year&gt;".</span>
          <span v-if="errors.member_since" class="ds-field-error-text">{{ errors.member_since }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Quote (optional)</span>
          <span class="ds-textarea-control">
            <textarea v-model="form.quote" rows="4" class="ds-textarea" placeholder="A short personal line, not a biography."></textarea>
          </span>
          <span v-if="errors.quote" class="ds-field-error-text">{{ errors.quote }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Display order</span>
          <span class="ds-field-control"><input v-model="form.display_order" type="number" class="ds-field-input" /></span>
          <span class="ds-field-hint">Lower numbers appear first on the public committee page.</span>
          <span v-if="errors.display_order" class="ds-field-error-text">{{ errors.display_order }}</span>
        </label>

        <label class="ds-checkbox">
          <input v-model="form.is_active" type="checkbox" />
          <span class="ds-checkbox-box">✓</span>
          <span class="ds-checkbox-label">Active (shown on the public committee page)</span>
        </label>

        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton to="/admin/content/committee" variant="ghost">Cancel</BaseButton>
          <BaseButton type="button" class="save-committee-member" :disabled="saving" @click="save">
            {{ saving ? 'Saving…' : 'Save' }}
          </BaseButton>
        </div>
      </div>
    </template>
    </div>

    <AvatarCropModal
      v-model="cropModalOpen"
      :file="pendingPhotoFile"
      :aspect-ratio="PORTRAIT_ASPECT_RATIO"
      @cropped="onPhotoCropped"
    />
  </div>
</template>
