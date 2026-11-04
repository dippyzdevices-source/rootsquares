<script setup lang="ts">
import { computed, useId } from 'vue'

// Design v3 meter (`.bx-meter` + `.bx-pbar`): label left, value text right, 3px brass bar. Used for usage against a plan limit.
const props = defineProps<{ label: string; valueText: string; percent: number }>()
const id = useId()
const pct = computed(() => Math.max(0, Math.min(100, props.percent)))
</script>

<template>
  <div class="bx-meter">
    <div><span :id="id">{{ label }}</span><span class="bs-mute">{{ valueText }}</span></div>
    <div class="bx-pbar" role="progressbar" :aria-labelledby="id" :aria-valuenow="pct" aria-valuemin="0" aria-valuemax="100" :aria-valuetext="valueText"><i :style="{ width: pct + '%' }" /></div>
  </div>
</template>
