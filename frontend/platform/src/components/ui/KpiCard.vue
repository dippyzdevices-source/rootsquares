<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'

// Mirrors design/components/data/KpiCard.jsx
withDefaults(defineProps<{ label: string; value: string; delta?: string; trend?: 'up' | 'down' | 'flat'; deltaLabel?: string }>(), { trend: 'flat' })
const ICON = { up: 'arrow-up', down: 'arrow-down', flat: 'minus' } as const
</script>

<template>
  <div class="rs-card">
    <div class="rs-kpi">
      <span class="rs-kpi__label">{{ label }}</span>
      <span class="rs-kpi__value">{{ value }}</span>
      <span v-if="delta" class="rs-kpi__delta" :class="`rs-kpi__delta--${trend}`">
        <AppIcon :name="ICON[trend]" :size="16" />{{ delta }}<span v-if="deltaLabel" class="rs-muted" style="font-weight: 400"> {{ deltaLabel }}</span>
      </span>
    </div>
  </div>
</template>
