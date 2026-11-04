<script setup lang="ts">
// Design v3 key-value list (`.bx-kv`): 140px label column, value column; real <dl> semantics.
defineProps<{ rows: [string, string][] }>()
</script>

<template>
  <dl class="bx-kv">
    <template v-for="[k, v] in rows" :key="k"><dt>{{ k }}</dt><dd><slot :name="k" :value="v">{{ v }}</slot></dd></template>
  </dl>
</template>
