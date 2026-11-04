<script setup lang="ts" generic="T extends Record<string, any>">
import { computed, ref } from 'vue'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'

// Mirrors design/components/data/Table.jsx (.rs-table). Cells are rendered with the `cell-<key>` slot, or the row value.
export interface Column { key: string; label: string; sortable?: boolean; align?: 'end'; primary?: boolean; aside?: boolean }
type Sort = { key: string; dir: 'asc' | 'desc' } | null

const props = defineProps<{ columns: Column[]; rows: T[]; rowKey?: string; dense?: boolean; caption?: string; loading?: boolean; defaultSort?: Sort }>()

const sort = ref<Sort>(props.defaultSort ?? null)
const key = computed(() => props.rowKey ?? 'id')
const cmp = (a: unknown, b: unknown) =>
  typeof a === 'number' && typeof b === 'number' ? a - b : String(a).localeCompare(String(b), undefined, { numeric: true })
const data = computed(() => {
  const s = sort.value
  return s ? [...props.rows].sort((a, b) => (s.dir === 'asc' ? 1 : -1) * cmp(a[s.key], b[s.key])) : props.rows
})
function toggle(k: string) {
  const s = sort.value
  sort.value = s && s.key === k ? (s.dir === 'asc' ? { key: k, dir: 'desc' } : null) : { key: k, dir: 'asc' }
}
const dirOf = (k: string) => (sort.value?.key === k ? sort.value.dir : null)
</script>

<template>
  <div class="rs-tablewrap">
    <div v-if="$slots.tools" class="rs-table__tools"><slot name="tools" /></div>
    <div class="rs-tablescroll">
      <table class="rs-table" :class="dense && 'rs-table--dense'">
        <caption v-if="caption" class="rs-sr">{{ caption }}</caption>
        <thead>
          <tr>
            <th v-for="c in columns" :key="c.key" scope="col" :aria-sort="dirOf(c.key) ? (dirOf(c.key) === 'asc' ? 'ascending' : 'descending') : c.sortable ? 'none' : undefined">
              <button v-if="c.sortable" type="button" :class="c.align === 'end' && 'rs-num'" @click="toggle(c.key)">
                {{ c.label }}<AppIcon :name="dirOf(c.key) === 'asc' ? 'chevron-up' : dirOf(c.key) === 'desc' ? 'chevron-down' : 'sort'" :size="16" :style="{ opacity: dirOf(c.key) ? 1 : 0.5 }" />
              </button>
              <span v-else :class="c.align === 'end' && 'rs-num'">{{ c.label }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-if="loading">
            <tr v-for="i in 4" :key="i"><td v-for="c in columns" :key="c.key"><span class="rs-skel" style="height: 14px; width: 70%" /></td></tr>
          </template>
          <template v-else>
            <tr v-for="r in data" :key="r[key]">
              <td v-for="c in columns" :key="c.key" :data-label="c.label" :data-primary="c.primary ? '' : undefined" :data-aside="c.aside ? '' : undefined" :class="c.align === 'end' && 'rs-num'">
                <slot :name="`cell-${c.key}`" :row="r">{{ r[c.key] }}</slot>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <slot v-if="!loading && data.length === 0" name="empty" />
    <div v-if="$slots.footer" class="rs-table__foot"><slot name="footer" /></div>
  </div>
</template>
