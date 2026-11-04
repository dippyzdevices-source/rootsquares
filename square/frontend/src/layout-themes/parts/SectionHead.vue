<script setup lang="ts">
import { activeLayout } from '../layouts'

// The heading of a home section in the theme's style: rule (title with a line under), center, num (numbered, heavy top rule), hand (handwritten
// kicker, wavy underline), caps (spaced capitals between double rules), pill (small label above the title).
const props = defineProps<{ n: number; title: string; sub?: string; link?: [string, string] | null; big?: boolean }>()
const kind = activeLayout!.sh
// The handwritten kicker is one short line: the first sentence of the intro, cut at 48 characters.
const kicker = (props.sub ?? '').split(/(?<=[.!?])\s/)[0]!.slice(0, 48).trim()
</script>

<template>
  <header class="lt-sh" :class="[`lt-shk-${kind}`, { 'lt-sh-big': big }]">
    <span v-if="kind === 'num'" class="lt-sh-n">{{ big ? '—' : `0${n} /` }}</span>
    <span v-if="kind === 'soft'" class="lt-sh-dot lt-nui-4" aria-hidden="true" />
    <div class="lt-sh-main">
      <span v-if="kind === 'pill'" class="lt-sh-pill">{{ title }}</span>
      <span v-else-if="kind === 'hand' && kicker" class="lt-sh-hand-l">{{ kicker }}</span>
      <h2 class="lt-sh-title">{{ title }}</h2>
      <p v-if="sub && kind !== 'hand'" class="lt-sh-sub">{{ sub }}</p>
    </div>
    <router-link v-if="link" :to="link[1]" class="lt-sh-link" :class="{ 'lt-nu-4': kind === 'soft' }">{{ link[0] }} →</router-link>
  </header>
</template>
