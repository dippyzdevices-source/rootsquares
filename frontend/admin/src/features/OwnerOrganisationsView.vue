<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import OcHead from '@/components/OcHead.vue'
import OcPill from '@rootsquares/ui/components/OcPill.vue'
import OcSearch from '@/components/OcSearch.vue'
import StateGate from '@rootsquares/ui/components/StateGate.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/errorText'
import { type SquareStatus } from '@rootsquares/ui/types/platformTypes'
import { type OwnerOrg } from '../adminTypes'
import { adminApi as platform } from '@/adminApi'

// Owner console, Organisations (platform admin only), from GET /owner/organizations. Restyled in W11-R75 from "Console Organisations.html":
// a monogram with the number of squares, the squares as a stack with status pills, and each row a card on narrow screens.
const { t } = useI18n()
const { date } = useFormat()
const rows = ref<OwnerOrg[]>([])
const loading = ref(true)
const error = ref('')
const q = ref('')

async function load() {
  loading.value = true
  try { rows.value = await platform.ownerOrganizations(); error.value = '' } catch (e) { error.value = errorText(t, e) }
  loading.value = false
}
onMounted(load)
const list = computed(() => rows.value.filter((r) => `${r.name} ${r.owner_email ?? ''}`.toLowerCase().includes(q.value.toLowerCase())))
const state = computed(() => (loading.value ? 'loading' : error.value ? 'error' : list.value.length ? 'default' : 'empty'))
const day = (iso: string) => date(iso, { day: 'numeric', month: 'short', year: 'numeric' })
const TONE: Record<SquareStatus, 'ok' | 'warn' | 'bad'> = { ready: 'ok', provisioning: 'warn', failed: 'bad' }
</script>

<template>
  <OcHead :title="t('own.orgs.title')" :sub="t('own.orgs.sub', { n: rows.length })" />
  <div class="oc-tools"><OcSearch v-model="q" :placeholder="t('own.orgs.searchPh')" :label="t('common.search')" /></div>
  <StateGate :state="state" :rows="4" :empty-title="t('own.people.emptyTitle')" :empty-text="t('own.people.emptyText')" @retry="load">
    <div class="oc-card">
      <table class="oc-tbl">
        <thead>
          <tr><th>{{ t('own.orgs.colName') }}</th><th>{{ t('own.orgs.colOwner') }}</th><th>{{ t('own.orgs.colMembers') }}</th><th>{{ t('own.orgs.colSquares') }}</th><th>{{ t('own.orgs.colCreated') }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in list" :key="r.id">
            <td class="pri" :data-label="t('own.orgs.colName')">
              <div class="oc-nm">
                <span class="oc-mono" aria-hidden="true">{{ r.name.trim().charAt(0).toUpperCase() }}</span>
                <div><b>{{ r.name }}</b><small>{{ t('own.orgs.squaresCount', { n: r.squares.length }, r.squares.length) }}</small></div>
              </div>
            </td>
            <td :data-label="t('own.orgs.colOwner')">{{ r.owner_email }}</td>
            <td :data-label="t('own.orgs.colMembers')">{{ r.members }}</td>
            <td class="wide" :data-label="t('own.orgs.colSquares')">
              <span v-if="!r.squares.length" class="oc-mut">{{ t('own.orgs.none') }}</span>
              <div v-else class="oc-stack">
                <span v-for="s in r.squares" :key="s.id" class="oc-row"><RouterLink :to="`/squares/${s.id}`" class="oc-link">{{ s.name }}</RouterLink><OcPill :tone="TONE[s.status]">{{ t(`plat.owner.st.${s.status}`) }}</OcPill></span>
              </div>
            </td>
            <td class="oc-mut" :data-label="t('own.orgs.colCreated')">{{ day(r.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </StateGate>
</template>
