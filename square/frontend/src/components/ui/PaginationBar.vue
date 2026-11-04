<script setup lang="ts">
// The one pager for every data table. Hidden when there is only one page.
defineProps<{ page: number; totalPages: number; total?: number }>()
const emit = defineEmits<{ 'update:page': [page: number] }>()
</script>

<template>
  <nav v-if="totalPages > 1" class="ds-pagination ds-scope" aria-label="Pagination">
    <div class="ds-pagination-group">
      <button type="button" class="ds-page-step" :disabled="page <= 1" @click="emit('update:page', page - 1)">Previous</button>
      <span class="ds-meta">Page {{ page }} of {{ totalPages }}<template v-if="total !== undefined"> ({{ total }} total)</template></span>
      <button type="button" class="ds-page-step" :disabled="page >= totalPages" @click="emit('update:page', page + 1)">Next</button>
    </div>
  </nav>
</template>
