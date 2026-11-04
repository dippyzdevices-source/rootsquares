<script setup lang="ts">
import { computed, useId } from 'vue'

// Mirrors design/components/data/Chart.jsx: series differ by pattern/dash as well as colour; an sr-only table repeats the data.
const props = withDefaults(defineProps<{
  type?: 'bar' | 'line'
  categories: string[]
  series: { name: string; values: number[] }[]
  height?: number
  ariaLabel: string
  format?: (n: number) => string
}>(), { type: 'bar', height: 220, format: (n: number) => String(n) })

const COL = ['var(--color-accent)', 'var(--color-info)', 'var(--color-warning)']
const DASH = [undefined, '6 4', '2 4']
const uid = useId().replace(/:/g, '')
const W = 600, L = 48, R = 8, T = 12, B = 28
const top = computed(() => {
  const max = Math.max(...props.series.flatMap((s) => s.values)) * 1.1 || 1
  return Math.ceil(max / 1000) * 1000 || max
})
const x0 = L, x1 = W - R
const y = (v: number) => T + (props.height - T - B) * (1 - v / top.value)
const bw = computed(() => (x1 - x0) / props.categories.length)
const ticks = computed(() => [0, 0.25, 0.5, 0.75, 1].map((f) => f * top.value))
</script>

<template>
  <div>
    <svg class="rs-chart" :viewBox="`0 0 ${W} ${height}`" role="img" :aria-label="ariaLabel">
      <defs>
        <template v-for="(s, i) in series" :key="s.name">
          <pattern v-if="i > 0" :id="uid + i" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="var(--color-surface)" /><rect width="3" height="6" :fill="COL[i]" />
          </pattern>
        </template>
      </defs>
      <g v-for="tk in ticks" :key="tk">
        <line :x1="x0" :x2="x1" :y1="y(tk)" :y2="y(tk)" stroke="var(--color-border)" />
        <text :x="x0 - 8" :y="y(tk) + 4" text-anchor="end" font-size="11" fill="var(--color-text-muted)">{{ format(tk) }}</text>
      </g>
      <text v-for="(c, i) in categories" :key="c" :x="x0 + bw * (i + 0.5)" :y="height - 8" text-anchor="middle" font-size="11" fill="var(--color-text-muted)">{{ c }}</text>
      <template v-if="type === 'bar'">
        <template v-for="(s, si) in series" :key="s.name">
          <rect
            v-for="(v, i) in s.values" :key="i"
            :x="x0 + bw * i + bw * 0.15 + ((bw * 0.7) / series.length) * si" :y="y(v)"
            :width="(bw * 0.7) / series.length - 2" :height="y(0) - y(v)" rx="3"
            :fill="si === 0 ? COL[0] : `url(#${uid}${si})`" :stroke="COL[si]" :stroke-width="si === 0 ? 0 : 1.5"
          />
        </template>
      </template>
      <template v-else>
        <g v-for="(s, si) in series" :key="s.name">
          <polyline fill="none" :stroke="COL[si]" stroke-width="2.5" :stroke-dasharray="DASH[si]" stroke-linejoin="round" :points="s.values.map((v, i) => `${x0 + bw * (i + 0.5)},${y(v)}`).join(' ')" />
        </g>
      </template>
    </svg>
    <div class="rs-legend">
      <span v-for="(s, i) in series" :key="s.name">
        <svg width="22" height="12" aria-hidden="true">
          <rect v-if="type === 'bar'" width="22" height="12" rx="2" :fill="i === 0 ? COL[0] : `url(#${uid}${i})`" :stroke="COL[i]" stroke-width="1.5" />
          <line v-else x1="0" x2="22" y1="6" y2="6" :stroke="COL[i]" stroke-width="2.5" :stroke-dasharray="DASH[i]" />
        </svg>{{ s.name }}
      </span>
    </div>
    <table class="rs-sr">
      <caption>{{ ariaLabel }}</caption>
      <thead><tr><th /><th v-for="s in series" :key="s.name">{{ s.name }}</th></tr></thead>
      <tbody><tr v-for="(c, i) in categories" :key="c"><th>{{ c }}</th><td v-for="s in series" :key="s.name">{{ format(s.values[i]!) }}</td></tr></tbody>
    </table>
  </div>
</template>
