<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { taxSplit, usd } from '@rootsquares/ui/mock/pricing'

// "Includes 25% tax: $119.20 + $29.80" under a price (W13-R51, ADR 060). Nothing when no tax is inside the price (percent 0 or unknown).
const props = defineProps<{ minor: number; percent?: number }>()
const { t } = useI18n()
const split = computed(() => taxSplit(props.minor, props.percent ?? 0))
</script>

<template>
  <span v-if="percent && percent > 0 && minor > 0" class="bs-mute" style="display: block; font-size: var(--text-xs)">{{ t('tax.included', { percent, net: usd(split.net), tax: usd(split.tax) }) }}</span>
</template>
