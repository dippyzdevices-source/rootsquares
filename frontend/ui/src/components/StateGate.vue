<script setup lang="ts">
import AppIcon from './AppIcon.vue'
import { useI18n } from 'vue-i18n'
import AppAlert from './AppAlert.vue'
import DataRow from './DataRow.vue'

// Design v3 state gate (E.jsx Gate): loading = skeleton rows, empty = centred message, error = danger alert with retry; otherwise the content.
withDefaults(defineProps<{ state: string; rows?: number; emptyTitle: string; emptyText: string; plain?: boolean }>(), { rows: 3 })
const emit = defineEmits<{ retry: [] }>()
const { t } = useI18n()
</script>

<template>
  <div v-if="state === 'loading'" class="bx-list"><DataRow v-for="i in rows" :key="i" loading /></div>
  <div v-else-if="state === 'empty'" class="bx-list">
    <div class="bx-dr" style="display: block; text-align: center; padding: 22px 12px">
      <b style="font-weight: 500">{{ emptyTitle }}</b>
      <div class="s" style="margin: 4px 0 0">{{ emptyText }}</div>
    </div>
  </div>
  <AppAlert v-else-if="state === 'error'" tone="danger" :title="t('bx.errorTitle')">
    {{ t('bx.errorText') }}
    <template #action><button type="button" class="rs-btn rs-btn--secondary rs-btn--sm" @click="emit('retry')"><AppIcon name="refresh" />{{ t('bx.retry') }}</button></template>
  </AppAlert>
  <slot v-else />
</template>
