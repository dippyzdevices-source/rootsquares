<script setup lang="ts">
import SettingsSectionNav from '../../components/SettingsSectionNav.vue'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import SettingsBackButton from '../../components/SettingsBackButton.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import { invalidateLookup } from '../../composables/useLookup'
import { useToast } from '../../composables/useToast'
import {
  createLookupValue,
  deleteLookupValue,
  fetchAdminLookup,
  fetchLookupLists,
  reorderLookupValues,
  LookupValidationError,
  updateLookupValue,
  type AdminLookupValue,
  type LookupListInfo,
} from '../../services/lookupsApi'

// Generic editor for every admin-managed option list (backend `lookup_values`). A new list shows
// up here automatically once it is registered in `app/lookups/registry.py`.
const toast = useToast()
const lists = ref<LookupListInfo[]>([])
const listKey = ref('')
const rows = ref<AdminLookupValue[]>([])
const loading = ref(true)
const error = ref(false)

// Side index (design: Lists Navigation, D/E): lists grouped by area, filtered by a search box.
const listSearch = ref('')
const railRef = ref<HTMLElement | null>(null)
const groupedLists = computed(() => {
  const q = listSearch.value.trim().toLowerCase()
  const groups = new Map<string, LookupListInfo[]>()
  for (const l of lists.value) {
    if (q && !l.title.toLowerCase().includes(q)) continue
    const g = l.group ?? 'Other'
    groups.set(g, [...(groups.get(g) ?? []), l])
  }
  return [...groups].map(([name, items]) => ({ name, items }))
})

// "/" jumps to the list search, like the design's keyboard hint.
function onSlash(e: KeyboardEvent) {
  const el = e.target as HTMLElement | null
  if (e.key !== '/' || el?.closest('input, textarea, [contenteditable]')) return
  e.preventDefault()
  railRef.value?.querySelector<HTMLInputElement>('input')?.focus()
}
onMounted(() => window.addEventListener('keydown', onSlash))
onUnmounted(() => window.removeEventListener('keydown', onSlash))
const currentList = computed(() => lists.value.find((l) => l.key === listKey.value))
const isFixed = computed(() => !!currentList.value?.fixed)

const editing = ref<AdminLookupValue | null>(null)
const showForm = ref(false)
const form = ref({ value: '', label: '' })
const errors = ref<Record<string, string>>({})
const saving = ref(false)
const deleteTarget = ref<AdminLookupValue | null>(null)

async function loadRows() {
  if (!listKey.value) return
  loading.value = true
  error.value = false
  try {
    rows.value = await fetchAdminLookup(listKey.value)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    lists.value = await fetchLookupLists()
    listKey.value = lists.value[0]?.key ?? ''
  } catch {
    error.value = true
    loading.value = false
  }
})
watch(listKey, loadRows)

function openNew() {
  editing.value = null
  form.value = { value: '', label: '' }
  errors.value = {}
  showForm.value = true
}

function openEdit(row: AdminLookupValue) {
  editing.value = row
  form.value = { value: row.value, label: row.label }
  errors.value = {}
  showForm.value = true
}

async function save() {
  saving.value = true
  errors.value = {}
  try {
    if (editing.value) {
      await updateLookupValue(listKey.value, editing.value.id, { label: form.value.label })
    } else {
      await createLookupValue(listKey.value, { value: form.value.value, label: form.value.label })
    }
    invalidateLookup(listKey.value)
    showForm.value = false
    toast.success('Saved')
    await loadRows()
  } catch (e) {
    if (e instanceof LookupValidationError) errors.value = e.errors
    else toast.error('Could not save this value')
  } finally {
    saving.value = false
  }
}

async function toggleActive(row: AdminLookupValue) {
  try {
    await updateLookupValue(listKey.value, row.id, { is_active: !row.is_active })
    invalidateLookup(listKey.value)
    await loadRows()
  } catch {
    toast.error('Could not update this value')
  }
}

// Hide/Show is always shown too; a value the system relies on can't be hidden.
function hideBlockedReason(row: AdminLookupValue): string | null {
  return row.protected && row.is_active ? 'Built into the system — it can be reworded but not hidden.' : null
}

// Delete is always shown; it is disabled (with the reason as a tooltip) when the value can't go.
function deleteBlockedReason(row: AdminLookupValue): string | null {
  if (row.protected) return 'Built into the system — it can be reworded but not deleted.'
  if (row.usage_count > 0) return `Used by ${row.usage_count} record${row.usage_count === 1 ? '' : 's'} — hide it instead.`
  return null
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await deleteLookupValue(listKey.value, deleteTarget.value.id)
    invalidateLookup(listKey.value)
    deleteTarget.value = null
    toast.success('Value deleted')
    await loadRows()
  } catch {
    toast.error('Could not delete this value')
  }
}

// Reordering: drag a row by its handle, or focus the handle and press ↑/↓ (touch screens get
// small up/down buttons instead). The list reorders in place right away and is saved with one
// request; if saving fails the old order comes back.
const dragId = ref<number | null>(null)
const overId = ref<number | null>(null)

async function applyOrder(next: AdminLookupValue[]) {
  const previous = rows.value
  rows.value = next
  try {
    await reorderLookupValues(listKey.value, next.map((r) => r.id))
    invalidateLookup(listKey.value)
  } catch {
    rows.value = previous
    toast.error('Could not save the new order')
  }
}

function moveRow(fromId: number, toId: number) {
  const next = [...rows.value]
  const from = next.findIndex((r) => r.id === fromId)
  const to = next.findIndex((r) => r.id === toId)
  if (from < 0 || to < 0 || from === to) return
  const [item] = next.splice(from, 1)
  next.splice(to, 0, item)
  void applyOrder(next)
}

function nudge(row: AdminLookupValue, direction: -1 | 1) {
  const index = rows.value.findIndex((r) => r.id === row.id)
  const target = rows.value[index + direction]
  if (target) moveRow(row.id, target.id)
}

function onDragStart(e: DragEvent, row: AdminLookupValue) {
  dragId.value = row.id
  e.dataTransfer?.setData('text/plain', String(row.id))
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}
function onDragOver(e: DragEvent, row: AdminLookupValue) {
  if (dragId.value === null) return
  e.preventDefault()
  overId.value = row.id
}
function onDrop(row: AdminLookupValue) {
  if (dragId.value !== null && dragId.value !== row.id) moveRow(dragId.value, row.id)
  onDragEnd()
}
function onDragEnd() {
  dragId.value = null
  overId.value = null
}
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Settings</h1>
        <p class="ds-intro">Site-wide settings and content that do not change often.</p>
      </div>

      <SettingsSectionNav />

      <div class="lists-wrap">
        <div class="lists-layout">
          <aside ref="railRef" class="lists-rail" aria-label="Lists">
            <BaseSearchField v-model="listSearch" size="sm" placeholder="Search lists" aria-label="Search lists" />
            <p v-if="groupedLists.length === 0" class="ds-meta lists-none">No list matches.</p>
            <template v-for="group in groupedLists" :key="group.name">
              <div class="lists-group">{{ group.name }}</div>
              <button
                v-for="l in group.items"
                :key="l.key"
                type="button"
                class="lists-item"
                :class="{ 'lists-item-on': l.key === listKey }"
                :aria-current="l.key === listKey ? 'true' : undefined"
                @click="listKey = l.key"
              >
                <span>{{ l.title }}</span>
                <b>{{ l.value_count }}</b>
              </button>
            </template>
          </aside>

          <section class="lists-main">
            <div class="lists-title-row">
              <h2 class="ds-display ds-display-s">{{ currentList?.title }}</h2>
              <div style="display: flex; align-items: center; gap: var(--ds-space-2); flex-wrap: wrap">
                <SettingsBackButton />
                <BaseButton v-if="currentList && !isFixed" size="sm" variant="primary" @click="openNew">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
                  New value
                </BaseButton>
              </div>
            </div>
            <p v-if="currentList" class="lists-meta">
              <span>{{ currentList.group }}</span><i /><span>{{ currentList.value_count }} values</span><i /><span>{{ currentList.description }}</span>
            </p>

            <BaseLoadingState v-if="loading" label="Loading values…" />
          <div v-else-if="error" class="ds-alert ds-alert-danger"><div>Couldn't load this list. Please try again shortly.</div></div>
          <div v-else class="ds-table-wrap">
            <div class="ds-table-scroll">
              <table class="ds-table">
                <thead>
                  <tr><th class="lists-handle-col" aria-label="Order"></th><th>Label</th><th>Stored value</th><th>Status</th><th></th></tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(row, index) in rows"
                    :key="row.id"
                    :class="{ 'lists-row-dragging': dragId === row.id, 'lists-row-over': overId === row.id && dragId !== row.id }"
                    @dragover="onDragOver($event, row)"
                    @drop.prevent="onDrop(row)"
                    @dragend="onDragEnd"
                  >
                    <td class="lists-handle-col">
                      <button
                        type="button"
                        class="lists-handle"
                        draggable="true"
                        :aria-label="`Reorder ${row.label} — drag, or press the up and down arrow keys`"
                        @dragstart="onDragStart($event, row)"
                        @keydown.up.prevent="nudge(row, -1)"
                        @keydown.down.prevent="nudge(row, 1)"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="9" cy="6" r="1" /><circle cx="15" cy="6" r="1" /><circle cx="9" cy="12" r="1" /><circle cx="15" cy="12" r="1" /><circle cx="9" cy="18" r="1" /><circle cx="15" cy="18" r="1" /></svg>
                      </button>
                    </td>
                    <td data-emphasis>{{ row.label }}</td>
                    <td class="ds-meta">{{ row.value }}</td>
                    <td><span class="ds-badge" :class="row.is_active ? 'ds-badge-success' : 'ds-badge-neutral'">{{ row.is_active ? 'Active' : 'Hidden' }}</span></td>
                    <td data-align="right">
                      <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                        <span class="lists-nudge">
                          <BaseIconButton variant="bare" size="sm" :label="`Move ${row.label} up`" :disabled="index === 0" @click="nudge(row, -1)">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6" /></svg>
                          </BaseIconButton>
                          <BaseIconButton variant="bare" size="sm" :label="`Move ${row.label} down`" :disabled="index === rows.length - 1" @click="nudge(row, 1)">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6" /></svg>
                          </BaseIconButton>
                        </span>
                        <BaseIconButton variant="bare" size="sm" :label="`Edit ${row.label}`" @click="openEdit(row)">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                        </BaseIconButton>
                        <span :title="hideBlockedReason(row) ?? undefined" class="lists-delete">
                          <BaseIconButton variant="bare" size="sm" :label="row.is_active ? `Hide ${row.label}` : `Show ${row.label}`" :disabled="!!hideBlockedReason(row)" @click="toggleActive(row)">
                            <svg v-if="row.is_active" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49" /><path d="M14.084 14.158a3 3 0 0 1-4.242-4.242" /><path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143" /><path d="m2 2 20 20" /></svg>
                            <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" /><circle cx="12" cy="12" r="3" /></svg>
                          </BaseIconButton>
                        </span>
                        <span :title="deleteBlockedReason(row) ?? undefined" class="lists-delete">
                          <BaseIconButton variant="danger" size="sm" :label="`Delete ${row.label}`" :disabled="!!deleteBlockedReason(row)" @click="deleteTarget = row">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /><line x1="10" x2="10" y1="11" y2="17" /><line x1="14" x2="14" y1="11" y2="17" /></svg>
                          </BaseIconButton>
                        </span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
            <p v-if="currentList" class="ds-meta lists-note">
              <template v-if="isFixed">These values are built into the system — you can reword and reorder them, not add, hide or delete.</template>
              <template v-else>Hiding a value removes it from new entries only; existing records keep it. Only values no record uses can be deleted.</template>
            </p>
          </section>
        </div>
      </div>
    </div>

    <BaseModal :model-value="!!deleteTarget" title="Delete value" @update:model-value="deleteTarget = null">
      <p class="ds-body">Delete "{{ deleteTarget?.label }}" from this list? This cannot be undone.</p>
      <div style="margin-top: var(--ds-space-4); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="deleteTarget = null">Cancel</BaseButton>
        <BaseButton type="button" variant="danger" @click="confirmDelete">Delete</BaseButton>
      </div>
    </BaseModal>

    <BaseModal v-model="showForm" :title="editing ? 'Edit value' : 'New value'">
      <form style="display: flex; flex-direction: column; gap: var(--ds-space-4)" @submit.prevent="save">
        <label class="ds-field">
          <span class="ds-field-label">Label</span>
          <span class="ds-field-control"><input v-model="form.label" type="text" maxlength="120" class="ds-field-input" /></span>
          <span v-if="errors.label" class="ds-field-error-text">{{ errors.label }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Stored value (cannot be changed later)</span>
          <span class="ds-field-control"><input v-model="form.value" type="text" maxlength="60" :disabled="!!editing" placeholder="e.g. insurance" class="ds-field-input" /></span>
          <span v-if="errors.value" class="ds-field-error-text">{{ errors.value }}</span>
        </label>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" @click="showForm = false">Cancel</BaseButton>
          <BaseButton type="submit" :disabled="saving">Save</BaseButton>
        </div>
      </form>
    </BaseModal>
  </div>
</template>

<style scoped>
/* Side index layout — design "Lists Navigation" D (light) / E (dark): the tokens switch with the theme. */
.lists-wrap { container-type: inline-size; }
.lists-layout { display: grid; grid-template-columns: 230px minmax(0, 1fr); gap: 32px; align-items: start; }
.lists-rail { position: relative; padding-right: 24px; border-right: 1px solid var(--ds-border-hairline); }
.lists-group { margin: 18px 0 5px 12px; font: 700 10px var(--ds-font-body, Karla, sans-serif); letter-spacing: 0.2em; text-transform: uppercase; color: var(--ds-text-faint); }
.lists-item { position: relative; display: flex; width: 100%; justify-content: space-between; align-items: baseline; gap: 8px; padding: 7px 12px; border: 0; border-radius: 8px; background: none; font-size: 14px; text-align: left; color: var(--ds-text-body); cursor: pointer; }
.lists-item b { font-weight: 500; font-size: 12px; color: var(--ds-text-faint); font-variant-numeric: tabular-nums; }
.lists-item:hover { background: var(--ds-surface-sunken); }
.lists-item-on { background: var(--ds-surface-primary-soft); color: var(--ds-text-heading); font-weight: 700; }
.lists-item-on::before { content: ''; position: absolute; left: -1px; top: 7px; bottom: 7px; width: 3px; border-radius: 3px; background: var(--ds-action-primary); }
.lists-item-on b { color: var(--ds-text-primary); }
.lists-none { margin: 14px 12px 0; }
.lists-main { min-width: 0; display: flex; flex-direction: column; gap: var(--ds-space-4); }
.lists-title-row { display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap; }
.lists-meta { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 0; font-size: 13px; color: var(--ds-text-muted); }
.lists-meta i { width: 3px; height: 3px; border-radius: 50%; background: var(--ds-text-faint); }
.lists-note { margin: 0; }
@container (max-width: 720px) {
  .lists-layout { grid-template-columns: minmax(0, 1fr); gap: 20px; }
  .lists-rail { padding-right: 0; border-right: 0; border-bottom: 1px solid var(--ds-border-hairline); padding-bottom: 12px; max-height: 18rem; overflow-y: auto; }
  .lists-item-on::before { left: 0; }
  .lists-handle-col { display: none; }
  .lists-nudge { display: inline-flex; }
}

.lists-handle-col { width: 36px; padding-right: 0 !important; }
.lists-handle { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border: 0; border-radius: 8px; background: none; color: var(--ds-text-faint); cursor: grab; }
.lists-handle:hover { background: var(--ds-surface-sunken); color: var(--ds-text-heading); }
.lists-handle:focus-visible { outline: 2px solid var(--ds-action-primary); outline-offset: 1px; }
.lists-handle:active { cursor: grabbing; }
.lists-row-dragging { opacity: 0.45; }
.lists-row-over { box-shadow: inset 0 2px 0 var(--ds-action-primary); }
.lists-delete { display: inline-flex; }
.lists-nudge { display: none; }
/* Touch screens and narrow layouts: no drag handle (dragging needs a mouse) — up/down buttons instead. */
@media (pointer: coarse) {
  .lists-handle-col { display: none; }
  .lists-nudge { display: inline-flex; }
}
</style>
