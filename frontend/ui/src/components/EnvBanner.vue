<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

// The environment strip above every page (W26-R25): says which copy of rootsquares this is, so staging, a local machine and (later) production are never mixed up.
// DISPLAY ONLY: nothing in the code behaves differently because of the label (the label comes from the server, which tells it in its start-up status answer (setting ENV_LABEL;
// empty = no strip, which is production). Staging is drawn in the product's warning colours, Local in its info colours; any other label gets the neutral look and just the word.
const props = defineProps<{ label?: string }>()
const { t, te } = useI18n()
const name = computed(() => (props.label ?? '').trim())
const kind = computed(() => name.value.toLowerCase())
const known = computed(() => kind.value === 'staging' || kind.value === 'local')
const sentence = computed(() => (known.value && te(`env.${kind.value}`) ? t(`env.${kind.value}`) : ''))
</script>

<template>
  <div v-if="name" class="env-bar" :class="known ? `env-bar--${kind}` : 'env-bar--other'" role="status" data-testid="env-banner">
    <b>{{ name }}</b><span v-if="sentence">{{ sentence }}</span>
  </div>
</template>
