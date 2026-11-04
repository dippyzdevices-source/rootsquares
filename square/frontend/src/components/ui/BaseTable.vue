<script setup lang="ts">
import BaseEmptyState from './BaseEmptyState.vue'

defineProps<{
  columns: { key: string; label: string }[]
  rows: Record<string, unknown>[]
  emptyMessage?: string
}>()
</script>

<template>
  <div class="overflow-x-auto rounded-lg border border-border">
    <table v-if="rows.length" class="w-full text-left text-sm">
      <thead class="border-b border-border bg-black/[0.02] dark:bg-white/[0.03]">
        <tr>
          <th
            v-for="column in columns"
            :key="column.key"
            class="px-4 py-3 font-medium text-text-secondary"
          >
            {{ column.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in rows" :key="index" class="border-b border-border last:border-0">
          <td v-for="column in columns" :key="column.key" class="px-4 py-3 text-text">
            <slot :name="`cell-${column.key}`" :row="row">
              {{ row[column.key] }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
    <BaseEmptyState v-else :title="emptyMessage ?? 'No data yet'" />
  </div>
</template>
