<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import RoleBadge from './RoleBadge.vue'
import RowMenu, { type MenuItem } from './RowMenu.vue'

// Design v3 Data row (`.bx-dr`, D.jsx DataRow): portrait - title + meta (wraps for long Norwegian titles) - role badge - actions menu.
// Loading = skeleton row. Wrap rows in `.bx-list`.
withDefaults(defineProps<{ name?: string; meta?: string; role?: 'owner' | 'admin' | 'editor' | 'viewer' | 'support'; menu?: (MenuItem | '-')[]; portrait?: boolean; loading?: boolean }>(), { portrait: true })
const emit = defineEmits<{ select: [id: string] }>()
const { t } = useI18n()
</script>

<template>
  <div v-if="loading" class="bx-dr" role="status" :aria-label="t('bx.loading')">
    <span class="bx-sk" style="width: 36px; height: 45px" />
    <div style="display: grid; gap: 6px"><span class="bx-sk" style="height: 12px; width: 50%" /><span class="bx-sk" style="height: 10px; width: 30%" /></div>
    <span /><span />
  </div>
  <div v-else class="bx-dr">
    <div v-if="portrait" class="bx-pt bx-pt--sm" aria-hidden="true" />
    <div style="min-width: 0"><div class="t" style="overflow-wrap: anywhere">{{ name }}</div><div class="s">{{ meta }}</div></div>
    <RoleBadge v-if="role" :role="role" />
    <RowMenu v-if="menu" :items="menu" @select="(id) => emit('select', id)" />
  </div>
</template>
