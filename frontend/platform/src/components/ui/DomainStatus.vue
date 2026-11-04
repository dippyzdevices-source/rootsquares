<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'

// Mirrors design/components/feedback/DomainStatus.jsx (copy comes from i18n)
const props = defineProps<{ domain: string; status: 'pending' | 'verifying' | 'live' | 'error'; records?: { type: string; name: string; value: string }[]; text?: string }>()
const { t } = useI18n()
const S = {
  pending: { icon: 'clock', chip: 'warning' },
  verifying: { icon: 'loader', chip: 'info' },
  live: { icon: 'circle-check', chip: 'success' },
  error: { icon: 'alert', chip: 'danger' },
} as const
const s = computed(() => S[props.status])
</script>

<template>
  <div class="rs-domain">
    <div class="rs-domain__row">
      <div style="display: flex; gap: 8px; align-items: center; min-width: 0"><AppIcon name="globe" /><b style="overflow-wrap: anywhere">{{ domain }}</b></div>
      <span class="rs-chip" :class="`rs-chip--${s.chip}`" role="status"><AppIcon :name="s.icon" :size="16" :class="status === 'verifying' && 'rs-spin'" />{{ t(`domain.${status}.label`) }}</span>
    </div>
    <p style="margin: 0">{{ text || t(`domain.${status}.text`) }}</p>
    <template v-if="status === 'pending' || status === 'error'">
      <div v-for="r in records" :key="r.type + r.name" class="rs-stack" style="gap: 4px">
        <span class="rs-hint">{{ r.type }} · {{ r.name }}</span>
        <div class="rs-code">{{ r.value }}</div>
      </div>
    </template>
  </div>
</template>
