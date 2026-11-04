<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'

// Design v3 tenant chips (D.jsx TenantChip): Trial = info, Active = success, Past due = warning, Suspended = danger; always icon + text (reuses .rs-chip--*).
defineProps<{ status: 'trial' | 'active' | 'pastDue' | 'suspended' }>()
const { t } = useI18n()
const MAP = { trial: ['info', 'info'], active: ['success', 'check'], pastDue: ['warning', 'alert'], suspended: ['danger', 'x'] } as const
</script>

<template>
  <span class="rs-chip" :class="`rs-chip--${MAP[status][0]}`"><AppIcon :name="MAP[status][1]" :size="12" />{{ t(`bx.tenant.${status}`) }}</span>
</template>
