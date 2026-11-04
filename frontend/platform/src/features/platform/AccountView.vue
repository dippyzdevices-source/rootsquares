<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import KeyValue from '@/components/ui/KeyValue.vue'
import SectionCard from '@rootsquares/ui/components/SectionCard.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { ApiError, platform } from '@/services/platform'
import { useAuthStore } from '@/stores/auth'
import { errorText } from './errorText'

// Your data (auth item G, GDPR): download everything the platform holds about you, or delete the account. An account with squares cannot be
// deleted until its squares are deleted, the 409 answer lists them.
const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const { push } = useToast()
const exporting = ref(false)
const exportError = ref('')
const confirm = ref('')
const deleting = ref(false)
const deleteError = ref('')
const blocking = ref<{ id: string; name: string; slug: string }[]>([])
const roleText = computed(() => {
  const u = auth.user
  if (!u) return ''
  const out: string[] = []
  for (const o of u.organizations) out.push(t('plat.account.orgRole', { role: o.role, org: o.name }))
  return out.join(', ') || t('plat.account.noRoles')
})
const canDelete = computed(() => !!auth.user && confirm.value.trim().toLowerCase() === auth.user.email.toLowerCase())

async function download() {
  exportError.value = ''
  exporting.value = true
  try {
    const blob = await platform.exportMyData()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `rootsquares-my-data-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    exportError.value = errorText(t, e)
  } finally {
    exporting.value = false
  }
}

async function remove() {
  deleteError.value = ''
  blocking.value = []
  deleting.value = true
  try {
    const left = await auth.deleteAccount(confirm.value.trim())
    push(left ? t('plat.account.deletedToast') : t('plat.account.deletedToastProvider'), 'success')
    await router.push('/')
  } catch (e) {
    deleteError.value = errorText(t, e)
    if (e instanceof ApiError && e.code === 'has_squares') blocking.value = (e.extra.squares as typeof blocking.value) ?? []
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <section class="mk-sec"><div class="au-col">
    <header style="display: grid; gap: 12px">
      <h1 class="bs-d" style="font-size: 40px">{{ t('plat.account.title') }}</h1>
      <hr class="rs-rule">
    </header>
    <KeyValue v-if="auth.user" :rows="[[t('plat.login.email'), auth.user.email], [t('plat.signup.name'), auth.user.name || '–'], [t('plat.account.role'), roleText]]" />

    <h2 class="bs-d" style="font-size: 24px">{{ t('plat.account.exportTitle') }}</h2>
    <p class="bs-mute" style="margin: 0">{{ t('plat.account.exportText') }}</p>
    <AppAlert v-if="exportError" tone="danger">{{ exportError }}</AppAlert>
    <div><AppButton icon="download" variant="secondary" :loading="exporting" @click="download">{{ t('plat.account.exportButton') }}</AppButton></div>

    <SectionCard :title="t('set.danger')" danger>
      <b style="font-weight: 500">{{ t('plat.account.deleteTitle') }}</b>
      <p class="bs-mute" style="margin: 0">{{ t('plat.account.deleteText') }}</p>
      <AppAlert v-if="deleteError" tone="danger">
        {{ deleteError }}
        <ul v-if="blocking.length" style="margin: 8px 0 0; padding-left: 20px">
          <li v-for="s in blocking" :key="s.id"><RouterLink :to="`/squares/${s.id}`">{{ s.name }}</RouterLink> ({{ s.slug }})</li>
        </ul>
      </AppAlert>
      <form class="rs-stack" style="gap: 16px" novalidate @submit.prevent="remove">
        <AppField v-model="confirm" type="email" :label="t('plat.account.confirmLabel')" :hint="t('plat.account.confirmHint')" autocomplete="off" />
        <div><AppButton icon="trash" type="submit" variant="danger" :loading="deleting" :disabled="!canDelete">{{ t('plat.account.deleteButton') }}</AppButton></div>
      </form>
    </SectionCard>
  </div></section>
</template>
