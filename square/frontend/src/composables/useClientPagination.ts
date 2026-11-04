import { computed, ref, watch, type Ref } from 'vue'

export const PAGE_SIZE = 20

// Pages a list that is already fully in memory (small admin tables). Clamps the page when the
// list shrinks (e.g. after a delete or a filter change).
export function useClientPagination<T>(items: Ref<T[]>, pageSize = PAGE_SIZE) {
  const page = ref(1)
  const totalPages = computed(() => Math.max(1, Math.ceil(items.value.length / pageSize)))
  const pageItems = computed(() => items.value.slice((page.value - 1) * pageSize, page.value * pageSize))
  watch(totalPages, (n) => {
    if (page.value > n) page.value = n
  })
  return { page, totalPages, pageItems, total: computed(() => items.value.length) }
}
