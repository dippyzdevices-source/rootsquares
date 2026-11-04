<script setup lang="ts">
// Design v3 section card used by the extension screens (E.jsx Card): `.bs-sec` with an uppercase header (title, optional right slot) and `.bx-body`.
defineProps<{ title: string; danger?: boolean }>()
</script>

<template>
  <section class="bs-sec" :style="danger ? { borderColor: 'var(--color-danger)' } : undefined">
    <header :style="danger ? { color: 'var(--color-danger)', borderColor: 'var(--color-danger)' } : undefined"><span>{{ title }}</span><slot name="right" /></header>
    <div class="bx-body"><slot /></div>
  </section>
</template>
