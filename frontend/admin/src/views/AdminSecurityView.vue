<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import OcHead from '@/components/OcHead.vue'
import OcPill from '@rootsquares/ui/components/OcPill.vue'
import StateGate from '@rootsquares/ui/components/StateGate.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { staffApi, type StaffSessionRow } from '@/adminApi'
import { errorText } from '@/errorText'
import { useStaffStore } from '@/stores/staff'

// The staff member's own logins (ADR 083): where the account is signed in, sign out the others, or sign out everywhere. The address is only a short tag.
const { t } = useI18n()
const router = useRouter()
const staff = useStaffStore()
const { date } = useFormat()
const rows = ref<StaffSessionRow[]>([])
const loading = ref(true)
const error = ref('')
const notice = ref('')
const dialog = ref(false)
const state = computed(() => (loading.value ? 'loading' : error.value ? 'error' : 'default'))
const when = (iso: string | null) => (iso ? date(iso, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '–')
const others = computed(() => rows.value.filter((r) => !r.current).length)

async function load() {
  loading.value = true
  try { rows.value = await staffApi.sessions(); error.value = '' } catch (e) { error.value = errorText(t, e) }
  loading.value = false
}
onMounted(load)
async function endOthers() {
  notice.value = ''
  try { notice.value = t('adm.security.othersDone', { n: await staffApi.revokeOthers() }); await load() } catch (e) { error.value = errorText(t, e) }
}
async function everywhere() {
  dialog.value = false
  try { await staffApi.logoutAll() } catch (e) { error.value = errorText(t, e); return }
  staff.clear()
  await router.push('/sign-in')
}
</script>

<template>
  <OcHead :title="t('adm.security.title')" :sub="t('adm.security.sub')" />
  <AppAlert v-if="notice" tone="success">{{ notice }}</AppAlert>
  <div class="oc-tools">
    <button type="button" class="oc-btn" :disabled="!others" @click="endOthers"><AppIcon name="out" :size="14" />{{ t('adm.security.others') }}</button>
    <button type="button" class="oc-btn" @click="dialog = true"><AppIcon name="out" :size="14" />{{ t('adm.security.everywhere') }}</button>
  </div>
  <StateGate :state="state" :rows="3" empty-title="" empty-text="" @retry="load">
    <div class="oc-card">
      <table class="oc-tbl">
        <thead><tr><th>{{ t('adm.security.colStarted') }}</th><th>{{ t('adm.security.colSeen') }}</th><th>{{ t('adm.security.colAddress') }}</th><th /></tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id">
            <td class="pri" :data-label="t('adm.security.colStarted')">{{ when(r.created_at) }}</td>
            <td :data-label="t('adm.security.colSeen')">{{ when(r.last_seen_at) }}</td>
            <td class="oc-mut" :data-label="t('adm.security.colAddress')">{{ r.ip_tag ?? '–' }}</td>
            <td><OcPill v-if="r.current" tone="ok">{{ t('adm.security.current') }}</OcPill></td>
          </tr>
        </tbody>
      </table>
    </div>
  </StateGate>
  <ConfirmDialog v-if="dialog" :title="t('adm.security.everywhereTitle')" :body="t('adm.security.everywhereText')" icon="out" :verb="t('adm.security.everywhere')" @cancel="dialog = false" @confirm="everywhere" />
</template>
