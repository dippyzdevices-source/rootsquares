<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import OcHead from '@/components/OcHead.vue'
import OcSearch from '@/components/OcSearch.vue'
import StateGate from '@rootsquares/ui/components/StateGate.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/errorText'
import { type OwnerUser } from '../adminTypes'
import { adminApi as platform } from '@/adminApi'

// Owner console, People (platform admin only): every account on the platform, from GET /owner/users. Restyled in W11-R75 from "Console People.html":
// initials avatar, Platform admin pill, and each row a card on narrow screens.
const { t } = useI18n()
const { date } = useFormat()
const rows = ref<OwnerUser[]>([])
const loading = ref(true)
const error = ref('')
const q = ref('')

async function load() {
  loading.value = true
  try { rows.value = await platform.ownerUsers(); error.value = '' } catch (e) { error.value = errorText(t, e) }
  loading.value = false
}
onMounted(load)
const list = computed(() => rows.value.filter((r) => `${r.name} ${r.email}`.toLowerCase().includes(q.value.toLowerCase())))
const state = computed(() => (loading.value ? 'loading' : error.value ? 'error' : list.value.length ? 'default' : 'empty'))
const day = (iso: string) => date(iso, { day: 'numeric', month: 'short', year: 'numeric' })
const initials = (r: OwnerUser) => (r.name || r.email).split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join('')
</script>

<template>
  <OcHead :title="t('own.people.title')" :sub="t('own.people.sub', { n: rows.length })" />
  <div class="oc-tools">
    <OcSearch v-model="q" :placeholder="t('own.people.searchPh')" :label="t('common.search')" />
  </div>
  <StateGate :state="state" :rows="4" :empty-title="t('own.people.emptyTitle')" :empty-text="t('own.people.emptyText')" @retry="load">
    <div class="oc-card">
      <table class="oc-tbl">
        <thead>
          <tr><th>{{ t('own.people.colPerson') }}</th><th>{{ t('own.people.colSignIn') }}</th><th>{{ t('own.people.colOrgs') }}</th><th>{{ t('own.people.colSessions') }}</th><th>{{ t('own.people.colCreated') }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in list" :key="r.id">
            <td class="pri" :data-label="t('own.people.colPerson')">
              <div class="oc-nm">
                <span class="oc-av" aria-hidden="true">{{ initials(r) }}</span>
                <div>
                  <RouterLink :to="`/people/${r.id}`" class="oc-link">{{ r.name || r.email }}</RouterLink>
                  <small>{{ r.email }}</small>
                </div>
              </div>
            </td>
            <td :data-label="t('own.people.colSignIn')">{{ r.sign_in }}</td>
            <td :data-label="t('own.people.colOrgs')">{{ r.organizations }}</td>
            <td :data-label="t('own.people.colSessions')">{{ r.active_sessions }}</td>
            <td class="oc-mut" :data-label="t('own.people.colCreated')">{{ day(r.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </StateGate>
</template>
