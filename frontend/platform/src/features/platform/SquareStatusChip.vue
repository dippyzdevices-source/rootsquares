<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import StatusChip from '@/components/ui/StatusChip.vue'
import type { SquareStatus } from '@/services/platform'

// provisioning = warning (clock), ready = success (check), failed = danger (alert); always icon plus text.
defineProps<{ status: SquareStatus; awaitingPayment?: boolean }>()
const { t } = useI18n()
const MAP = { provisioning: 'pending', ready: 'paid', failed: 'overdue' } as const
</script>

<template>
  <StatusChip :status="MAP[status]">{{ t(awaitingPayment ? 'plat.status.awaiting' : `plat.status.${status}`) }}</StatusChip>
</template>
