<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import FilterPills from '../../components/ui/FilterPills.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import { PAGE_SIZE } from '../../composables/useClientPagination'
import BaseModal from '../../components/ui/BaseModal.vue'
import {
  deleteAdminTestimonial,
  fetchAdminTestimonials,
  updateAdminTestimonial,
  type AdminTestimonial,
  type TestimonialStatus,
} from '../../services/adminTestimonialsApi'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const { label: testimonialStatusLabel } = useLookup('testimonial_status')
const testimonials = ref<AdminTestimonial[]>([])
const loading = ref(true)
const error = ref(false)
const deleteTarget = ref<AdminTestimonial | null>(null)
const viewTarget = ref<AdminTestimonial | null>(null)
const moderating = ref<number | null>(null)
const toast = useToast()
const route = useRoute()

const statusFilters = computed<{ value: TestimonialStatus | ''; label: string }[]>(() => [
  { value: '', label: 'All' },
  { value: 'pending', label: testimonialStatusLabel('pending') },
  { value: 'approved', label: testimonialStatusLabel('approved') },
  { value: 'rejected', label: testimonialStatusLabel('rejected') },
])
// Pre-selects the filter from a `?status=` query param (e.g. the dashboard's "Pending
// testimonials" card) so arriving here already shows the relevant subset, not every record.
const initialStatus = typeof route.query.status === 'string' ? route.query.status : ''
const search = ref('')
const activeFilter = ref<TestimonialStatus | ''>(
  statusFilters.value.some((opt) => opt.value === initialStatus) ? (initialStatus as TestimonialStatus | '') : '',
)

function truncate(text: string, max = 80): string {
  return text.length > max ? `${text.slice(0, max)}…` : text
}

function statusTone(status: TestimonialStatus): string {
  if (status === 'approved') return 'ds-badge-success'
  if (status === 'rejected') return 'ds-badge-danger'
  return 'ds-badge-warning'
}

const page = ref(1)
const totalPages = ref(1)
const total = ref(0)

// Filter/search changes go back to page 1 (the page watcher does the load when it moves).
function reload() {
  if (page.value !== 1) page.value = 1
  else load()
}

async function load() {
  loading.value = true
  error.value = false
  try {
    const data = await fetchAdminTestimonials(activeFilter.value || undefined, PAGE_SIZE, page.value, search.value.trim() || undefined)
    testimonials.value = data.items
    totalPages.value = data.total_pages
    total.value = data.total
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

async function approve(testimonial: AdminTestimonial) {
  moderating.value = testimonial.id
  try {
    await updateAdminTestimonial(testimonial.id, { status: 'approved', is_active: true })
    toast.success('Testimonial approved — now live on the homepage')
    await load()
  } catch {
    toast.error('Could not approve this testimonial')
  } finally {
    moderating.value = null
  }
}

async function reject(testimonial: AdminTestimonial) {
  moderating.value = testimonial.id
  try {
    await updateAdminTestimonial(testimonial.id, { status: 'rejected', is_active: false })
    toast.success('Testimonial rejected')
    await load()
  } catch {
    toast.error('Could not reject this testimonial')
  } finally {
    moderating.value = null
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await deleteAdminTestimonial(deleteTarget.value.id)
    toast.success('Testimonial deleted')
    deleteTarget.value = null
    await load()
  } catch {
    toast.error('Could not delete testimonial')
  }
}

watch(activeFilter, reload)
watch(page, load)
onMounted(load)
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
          <h1 class="ds-display ds-display-s">Testimonials</h1>
        </div>
        <BaseButton size="sm" to="/admin/testimonials/new" variant="secondary">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
          New testimonial
        </BaseButton>
      </div>

      <hr class="ds-section-line" />

      <div class="ds-toolbar">
        <FilterPills v-model="activeFilter" :options="statusFilters" label="Filter testimonials by status" />
        <BaseSearchField size="sm" class="ds-toolbar-search" v-model="search" placeholder="Search by name or quote…" aria-label="Search testimonials" @keyup.enter="reload" />
      </div>

      <BaseLoadingState v-if="loading" label="Loading testimonials…" />
      <BaseEmptyState
        v-else-if="error"
        title="Couldn't load testimonials"
        description="Please try again shortly."
      />
      <div v-else-if="testimonials.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
        <p class="ds-meta">{{ activeFilter || search.trim() ? 'No testimonials match this filter or search.' : 'No testimonials yet — add one to show it on the homepage.' }}</p>
      </div>
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead>
              <tr>
                <th>Author</th>
                <th>Quote</th>
                <th>Status</th>
                <th>Order</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="testimonial in testimonials" :key="testimonial.id">
                <td data-emphasis>{{ testimonial.author_name }}</td>
                <td>{{ truncate(testimonial.quote) }}</td>
                <td>
                  <span class="ds-badge" :class="statusTone(testimonial.status)">{{ testimonialStatusLabel(testimonial.status) }}</span>
                  <div class="ds-caption">{{ testimonial.is_active ? 'Shown on site' : 'Hidden' }}</div>
                </td>
                <td>{{ testimonial.sort_order }}</td>
                <td data-align="right">
                  <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                    <BaseIconButton variant="bare" size="sm" :label="`View testimonial from ${testimonial.author_name}`" @click="viewTarget = testimonial">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" /><circle cx="12" cy="12" r="3" /></svg>
                    </BaseIconButton>
                    <template v-if="testimonial.status === 'pending'">
                      <BaseIconButton variant="success"
                        size="sm"
                        :label="`Approve testimonial from ${testimonial.author_name}`"
                        :disabled="moderating === testimonial.id"
                        @click="approve(testimonial)"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
                      </BaseIconButton>
                      <BaseIconButton
                        variant="danger"
                        size="sm"
                        :label="`Reject testimonial from ${testimonial.author_name}`"
                        :disabled="moderating === testimonial.id"
                        @click="reject(testimonial)"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18" /><path d="M6 6l12 12" /></svg>
                      </BaseIconButton>
                    </template>
                    <BaseIconButton variant="bare" :to="`/admin/testimonials/${testimonial.id}/edit`" size="sm" :label="`Edit testimonial from ${testimonial.author_name}`">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                    </BaseIconButton>
                    <BaseIconButton
                      variant="danger"
                      type="button"
                      size="sm"
                      :label="`Delete testimonial from ${testimonial.author_name}`"
                      @click="deleteTarget = testimonial"
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
      title="Delete testimonial"
      @update:model-value="deleteTarget = null"
    >
      <p class="ds-body">Delete the testimonial from "{{ deleteTarget?.author_name }}"? This cannot be undone.</p>
      <div style="margin-top: var(--ds-space-4); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="deleteTarget = null">Cancel</BaseButton>
        <BaseButton type="button" @click="confirmDelete" variant="danger">Delete</BaseButton>
      </div>
    </BaseModal>

    <BaseModal
      :model-value="!!viewTarget"
      title="Testimonial"
      @update:model-value="viewTarget = null"
    >
      <div v-if="viewTarget" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <div style="display: flex; align-items: center; gap: var(--ds-space-2); flex-wrap: wrap">
          <span class="ds-badge" :class="statusTone(viewTarget.status)">{{ testimonialStatusLabel(viewTarget.status) }}</span>
          <span class="ds-caption">{{ viewTarget.is_active ? 'Shown on site' : 'Hidden' }}</span>
        </div>
        <blockquote class="ds-pullquote" style="padding: var(--ds-space-4) 0">
          <p style="font-size: var(--ds-text-title)">&ldquo;{{ viewTarget.quote }}&rdquo;</p>
          <footer>
            {{ viewTarget.author_name }}<template v-if="viewTarget.author_context">, {{ viewTarget.author_context }}</template>
          </footer>
        </blockquote>
        <img v-if="viewTarget.photo_url" :src="viewTarget.photo_url" alt="" style="width: 64px; height: 64px; border-radius: var(--ds-radius-pill); object-fit: cover" />
        <p class="ds-caption">Homepage display order: {{ viewTarget.sort_order }} (lower numbers appear first)</p>
      </div>
      <div style="margin-top: var(--ds-space-5); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="viewTarget = null">Close</BaseButton>
        <BaseButton :to="`/admin/testimonials/${viewTarget?.id}/edit`">Edit</BaseButton>
      </div>
    </BaseModal>
  </div>
</template>
