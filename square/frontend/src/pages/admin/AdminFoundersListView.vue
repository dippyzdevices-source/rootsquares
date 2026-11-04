<script setup lang="ts">
import SettingsSectionNav from '../../components/SettingsSectionNav.vue'
import SettingsBackButton from '../../components/SettingsBackButton.vue'
import { ref, onMounted, computed, watch } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import FilterPills from '../../components/ui/FilterPills.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import { useClientPagination } from '../../composables/useClientPagination'
import BaseModal from '../../components/ui/BaseModal.vue'
import {
  deleteAdminFounder,
  fetchAdminFounders,
  type AdminFounder,
} from '../../services/adminFoundersApi'
import { useToast } from '../../composables/useToast'

const toast = useToast()
const members = ref<AdminFounder[]>([])
const search = ref('')
const filter = ref('all')
const filterOptions = [{ value: 'all', label: 'All' }, { value: 'active', label: 'Active' }, { value: 'hidden', label: 'Hidden' }]
const visible = computed(() => {
  const f = filter.value
  const q = search.value.trim().toLowerCase()
  return members.value.filter((m) => (f === 'all' || (f === 'active') === m.is_active) && (!q || String(m.name ?? '').toLowerCase().includes(q) || String(m.sub_name ?? '').toLowerCase().includes(q) || String(m.role ?? '').toLowerCase().includes(q)))
})
const { page, totalPages, pageItems, total } = useClientPagination(visible)
watch([filter, search], () => (page.value = 1))
const loading = ref(true)
const error = ref(false)
const deleteTarget = ref<AdminFounder | null>(null)

async function load() {
  loading.value = true
  error.value = false
  try {
    members.value = (await fetchAdminFounders()).items
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await deleteAdminFounder(deleteTarget.value.id)
    toast.success('Founder deleted')
    deleteTarget.value = null
    await load()
  } catch {
    toast.error('Could not delete this founder')
  }
}

onMounted(load)
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
          <h1 class="ds-display ds-display-s">Settings</h1>
          <p class="ds-intro">Site-wide settings and content that do not change often.</p>
        </div>
      </div>

      <SettingsSectionNav />

      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <h2 class="ds-display ds-display-s">Founders</h2>
        <div style="display: flex; align-items: center; gap: var(--ds-space-2); flex-wrap: wrap">
          <SettingsBackButton />
          <BaseButton size="sm" to="/admin/content/founders/new" variant="secondary">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
            New founder
          </BaseButton>
        </div>
      </div>

      <div class="ds-toolbar">
        <FilterPills v-model="filter" :options="filterOptions" label="Filter founders by status" />
        <BaseSearchField size="sm" class="ds-toolbar-search" v-model="search" placeholder="Search by name or role…" aria-label="Search founders" />
      </div>

      <BaseLoadingState v-if="loading" label="Loading founders…" />
      <div v-else-if="error" class="ds-alert ds-alert-danger"><div>Couldn't load the founders. Please try again shortly.</div></div>
      <div v-else-if="members.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
        <p class="ds-meta">No founders yet — add one to show it on the About page.</p>
      </div>
      <div v-else-if="visible.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
        <p class="ds-meta">Nothing matches this filter or search.</p>
      </div>
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Role</th>
                <th data-align="right">Order</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="member in pageItems" :key="member.id">
                <td data-emphasis>{{ member.name }}</td>
                <td>{{ member.role }}</td>
                <td data-align="right">{{ member.display_order }}</td>
                <td><span class="ds-badge" :class="member.is_active ? 'ds-badge-success' : 'ds-badge-neutral'">{{ member.is_active ? 'Active' : 'Hidden' }}</span></td>
                <td data-align="right">
                  <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                    <BaseIconButton variant="bare" :to="`/admin/content/founders/${member.id}/edit`" size="sm" :label="`Edit ${member.name}`">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                    </BaseIconButton>
                    <BaseIconButton
                      variant="danger"
                      type="button"
                      size="sm"
                      :label="`Delete ${member.name}`"
                      @click="deleteTarget = member"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /><line x1="10" x2="10" y1="11" y2="17" /><line x1="14" x2="14" y1="11" y2="17" /></svg>
                    </BaseIconButton>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <PaginationBar v-model:page="page" :total-pages="totalPages" :total="total" />
    </div>

    <BaseModal :model-value="!!deleteTarget" title="Delete founder" @update:model-value="deleteTarget = null">
      <p class="ds-body">Delete "{{ deleteTarget?.name }}" from the founders? This cannot be undone.</p>
      <div style="margin-top: var(--ds-space-4); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="deleteTarget = null">Cancel</BaseButton>
        <BaseButton type="button" @click="confirmDelete" variant="danger">Delete</BaseButton>
      </div>
    </BaseModal>
  </div>
</template>
