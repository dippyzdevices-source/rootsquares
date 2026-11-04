<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import NewsSectionNav from '../../components/NewsSectionNav.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import FilterPills from '../../components/ui/FilterPills.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import { PAGE_SIZE } from '../../composables/useClientPagination'
import BaseModal from '../../components/ui/BaseModal.vue'
import { deleteAdminNews, fetchAdminNews, type AdminNewsArticle } from '../../services/adminNewsApi'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const { label: newsStatusLabel } = useLookup('news_status')
const articles = ref<AdminNewsArticle[]>([])
const search = ref('')
const stateFilter = ref('all')
const stateOptions = computed(() => [
  { value: 'all', label: 'All' },
  { value: 'published', label: newsStatusLabel('published') },
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'draft', label: newsStatusLabel('draft') },
  { value: 'archived', label: newsStatusLabel('archived') },
])
const filtering = computed(() => search.value.trim() !== '' || stateFilter.value !== 'all')
const loading = ref(true)
const error = ref(false)
const deleteTarget = ref<AdminNewsArticle | null>(null)
const toast = useToast()
const { label: categoryLabel } = useLookup('news_category')

function statusTone(status: string): string {
  if (status === 'published') return 'ds-badge-success'
  if (status === 'archived') return 'ds-badge-danger'
  return 'ds-badge-neutral'
}

const page = ref(1)
const totalPages = ref(1)
const total = ref(0)

async function load() {
  loading.value = true
  error.value = false
  try {
    const data = await fetchAdminNews(PAGE_SIZE, page.value, {
      q: search.value.trim() || undefined,
      status: stateFilter.value === 'all' ? undefined : stateFilter.value,
    })
    articles.value = data.items
    totalPages.value = data.total_pages
    total.value = data.total
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await deleteAdminNews(deleteTarget.value.id)
    toast.success('Article deleted')
    deleteTarget.value = null
    await load()
  } catch {
    toast.error('Could not delete article')
  }
}

// Search/filter changes go back to page 1 (the page watcher does the load when it moves).
function reload() {
  if (page.value !== 1) page.value = 1
  else load()
}

watch(stateFilter, reload)
watch(page, load)
onMounted(load)
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
          <h1 class="ds-display ds-display-s">News</h1>
        </div>
        <BaseButton size="sm" to="/admin/news/new" variant="secondary">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
          New article
        </BaseButton>
      </div>

      <NewsSectionNav />

      <div class="ds-toolbar">
        <FilterPills v-model="stateFilter" :options="stateOptions" label="Filter articles by status" />
        <BaseSearchField size="sm" class="ds-toolbar-search" v-model="search" placeholder="Search by title or summary…" aria-label="Search articles" @keyup.enter="reload" />
      </div>

      <BaseLoadingState v-if="loading" label="Loading articles…" />
      <BaseEmptyState
        v-else-if="error"
        title="Couldn't load articles"
        description="Please try again shortly."
      />
      <BaseEmptyState
        v-else-if="articles.length === 0 && !filtering"
        title="No articles yet"
        description="Create your first article to get started."
      />
      <div v-else-if="articles.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
        <p class="ds-meta">No articles match this filter or search.</p>
      </div>
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Status</th>
                <th>Category</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="article in articles" :key="article.id">
                <td data-emphasis>{{ article.title }}</td>
                <td><span class="ds-badge" :class="statusTone(article.status)">{{ newsStatusLabel(article.status) }}</span></td>
                <td>{{ article.category ? categoryLabel(article.category) : '—' }}</td>
                <td data-align="right">
                  <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                    <BaseIconButton variant="bare" :to="`/admin/news/${article.id}/edit`" size="sm" :label="`Edit ${article.title}`">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                    </BaseIconButton>
                    <BaseIconButton
                      variant="danger"
                      type="button"
                      size="sm"
                      :label="`Delete ${article.title}`"
                      @click="deleteTarget = article"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /><line x1="10" x2="10" y1="11" y2="17" /><line x1="14" x2="14" y1="11" y2="17" /></svg>
                    </BaseIconButton>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <PaginationBar v-model:page="page" :total-pages="totalPages" :total="total" />
    </div>

    <BaseModal
      :model-value="!!deleteTarget"
      title="Delete article"
      @update:model-value="deleteTarget = null"
    >
      <p class="ds-body">Delete "{{ deleteTarget?.title }}"? This cannot be undone.</p>
      <div style="margin-top: var(--ds-space-4); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="deleteTarget = null">Cancel</BaseButton>
        <BaseButton type="button" @click="confirmDelete" variant="danger">Delete</BaseButton>
      </div>
    </BaseModal>
  </div>
</template>
