<script setup lang="ts">
import { isBlankPhone, phonePrefix } from '../../utils/phone'
import { squareProfile } from '../../services/squareConfig'
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AvatarCropModal from '../../components/ui/AvatarCropModal.vue'
import BaseAvatar from '../../components/ui/BaseAvatar.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseFileButton from '../../components/ui/BaseFileButton.vue'
import BaseInput from '../../components/ui/BaseInput.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { useAuthStore } from '../../stores/auth'
import { useToast } from '../../composables/useToast'
import {
  fetchMyMember,
  saveMyMember,
  uploadMyPhoto,
  exportMyData,
  MemberNotFoundError,
  type MemberProfile,
} from '../../services/memberApi'

const auth = useAuthStore()
const router = useRouter()
const toast = useToast()

const loading = ref(true)
const profile = ref<MemberProfile | null>(null)
const form = ref({ name: '', phone: phonePrefix(), address: '' })
const saving = ref(false)
const saveError = ref('')
const exporting = ref(false)
const uploadingPhoto = ref(false)
const cropModalOpen = ref(false)
const pendingPhotoFile = ref<File | null>(null)

onMounted(async () => {
  try {
    profile.value = await fetchMyMember()
    form.value = {
      name: profile.value.name || auth.displayName || '',
      phone: profile.value.phone ?? phonePrefix(),
      address: profile.value.address ?? '',
    }
  } catch (err) {
    if (!(err instanceof MemberNotFoundError)) {
      toast.error('Could not load your profile.')
    } else {
      form.value.name = auth.displayName ?? ''
    }
  } finally {
    loading.value = false
  }
})

async function save() {
  saving.value = true
  saveError.value = ''
  try {
    const trimmedPhone = form.value.phone.trim()
    profile.value = await saveMyMember({
      name: form.value.name,
      phone: isBlankPhone(trimmedPhone) ? null : trimmedPhone,
      address: form.value.address || null,
    })
    toast.success('Contact details saved')
  } catch {
    saveError.value = 'Could not save your profile.'
  } finally {
    saving.value = false
  }
}

function handlePhotoSelect(domEvent: Event) {
  const input = domEvent.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  pendingPhotoFile.value = file
  cropModalOpen.value = true
  input.value = ''
}

async function handleCropped(blob: Blob) {
  cropModalOpen.value = false
  const file = new File([blob], 'profile-photo.jpg', { type: 'image/jpeg' })

  uploadingPhoto.value = true
  try {
    profile.value = await uploadMyPhoto(file)
    toast.success('Profile photo updated')
  } catch {
    toast.error('Could not upload this photo')
  } finally {
    uploadingPhoto.value = false
    pendingPhotoFile.value = null
  }
}

async function downloadExport() {
  exporting.value = true
  try {
    const data = await exportMyData()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${squareProfile.slug}-my-data.json`
    link.click()
    URL.revokeObjectURL(url)
  } catch {
    toast.error('Could not export your data')
  } finally {
    exporting.value = false
  }
}

async function signOut() {
  await auth.signOut()
  router.push('/')
}
</script>

<template>
  <div class="ds-scope">
    <div style="max-width: 620px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />My portal</span>
        <h1 class="ds-display ds-display-s">Settings</h1>
      </div>

      <BaseLoadingState v-if="loading" label="Loading your settings…" />

      <template v-else>
        <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
          <h2 class="ds-title">Contact details</h2>

          <div style="display: flex; align-items: center; gap: var(--ds-space-4); flex-wrap: wrap">
            <BaseAvatar :src="profile?.photo_url ?? auth.avatarUrl" :name="profile?.name ?? auth.displayName" size="xl" />
            <div style="display: flex; flex-direction: column; gap: var(--ds-space-2)">
              <BaseFileButton size="sm" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" :disabled="uploadingPhoto || !profile" style="align-self: flex-start" @change="handlePhotoSelect">
                {{ uploadingPhoto ? 'Uploading…' : profile?.photo_url ? 'Replace photo' : 'Upload photo' }}
              </BaseFileButton>
              <p v-if="!profile" class="ds-caption">Save your contact details first, then you can upload a photo.</p>
            </div>
          </div>

          <BaseInput v-model="form.name" label="Full name" />
          <BaseInput v-model="form.phone" label="Phone" placeholder="Phone" />
          <BaseInput v-model="form.address" label="Address" />
          <div v-if="saveError" class="ds-alert ds-alert-danger"><div>{{ saveError }}</div></div>
          <BaseButton type="button" style="align-self: flex-start" :disabled="saving" @click="save">
            {{ saving ? 'Saving…' : 'Save changes' }}
          </BaseButton>
        </div>

        <div class="ds-card ds-card-outline" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
          <h2 class="ds-title">Your data</h2>
          <p class="ds-meta">Download everything {{ squareProfile.name }} holds about you — profile, memberships, and orders.</p>
          <BaseButton type="button" variant="secondary" size="sm" class="export-my-data" style="align-self: flex-start" :disabled="exporting" @click="downloadExport">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
            {{ exporting ? 'Preparing…' : 'Export my data' }}
          </BaseButton>
        </div>

        <div class="ds-card ds-card-sunken" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
          <h2 class="ds-title">Account</h2>
          <div style="display: flex; gap: var(--ds-space-3); flex-wrap: wrap">
            <BaseButton to="/forgot-password" variant="secondary" size="sm">Change password</BaseButton>
            <BaseButton type="button" variant="ghost" size="sm" @click="signOut">Sign out</BaseButton>
          </div>
        </div>
      </template>
    </div>

    <AvatarCropModal v-model="cropModalOpen" :file="pendingPhotoFile" @cropped="handleCropped" />
  </div>
</template>
