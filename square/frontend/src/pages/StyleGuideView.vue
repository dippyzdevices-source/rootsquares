<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import BaseAlert from '../components/ui/BaseAlert.vue'
import BaseBadge from '../components/ui/BaseBadge.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseCard from '../components/ui/BaseCard.vue'
import BaseDrawer from '../components/ui/BaseDrawer.vue'
import BaseEmptyState from '../components/ui/BaseEmptyState.vue'
import BaseInput from '../components/ui/BaseInput.vue'
import BaseLoadingState from '../components/ui/BaseLoadingState.vue'
import BaseModal from '../components/ui/BaseModal.vue'
import BaseSelect from '../components/ui/BaseSelect.vue'
import BaseSkeleton from '../components/ui/BaseSkeleton.vue'
import BaseTable from '../components/ui/BaseTable.vue'
import BaseTabs from '../components/ui/BaseTabs.vue'
import ThemeToggle from '../components/ui/ThemeToggle.vue'
import { useToast } from '../composables/useToast'
import { useLookup } from '../composables/useLookup'

const apiStatus = ref<'checking' | 'ok' | 'error'>('checking')
const name = ref('')
const eventType = ref('')
const modalOpen = ref(false)
const drawerOpen = ref(false)
const activeTab = ref('upcoming')
const toast = useToast()

const alertVariant = computed(() => {
  if (apiStatus.value === 'ok') return 'success'
  if (apiStatus.value === 'error') return 'error'
  return 'info'
})

const { options: eventTypeOptions } = useLookup('event_type')

const orderColumns = [
  { key: 'order', label: 'Order' },
  { key: 'event', label: 'Event' },
  { key: 'status', label: 'Status' },
]

const orderRows = [
  { order: 'BCA-2026-000183', event: 'Durga Puja 2026', status: 'Paid' },
  { order: 'BCA-2026-000184', event: 'Mahalaya 2026', status: 'Pending' },
]

const tabs = [
  { id: 'upcoming', label: 'Upcoming' },
  { id: 'past', label: 'Past' },
]

onMounted(async () => {
  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL as string
    const response = await fetch(`${baseUrl}/api/health`)
    const data = await response.json()
    apiStatus.value = data.status === 'ok' ? 'ok' : 'error'
  } catch {
    apiStatus.value = 'error'
  }
})
</script>

<template>
  <main class="min-h-full bg-bg px-6 py-12">
    <div class="mx-auto max-w-3xl space-y-10">
      <header class="space-y-2">
        <div class="flex items-center justify-between">
          <h1 class="text-4xl font-semibold text-text">BCA Oslo</h1>
          <ThemeToggle />
        </div>
        <p class="text-text-secondary">
          Design foundation preview (BCA-010/012) — this page is a style guide, not a real
          route.
        </p>
        <p class="font-bengali text-xl text-text">স্বাগতম, বিসিএ অসলো</p>
        <p class="font-bengali-serif text-lg text-text-secondary">দুর্গা পূজা ২০২৬</p>
      </header>

      <BaseAlert :variant="alertVariant">Backend API: {{ apiStatus }}</BaseAlert>

      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text">Colors</h2>
        <div class="flex flex-wrap gap-3">
          <div class="h-16 w-16 rounded-md bg-primary" title="primary" />
          <div class="h-16 w-16 rounded-md bg-secondary" title="secondary" />
          <div class="h-16 w-16 rounded-md bg-accent" title="accent" />
          <div class="h-16 w-16 rounded-md border border-border bg-surface" title="surface" />
        </div>
      </section>

      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text">Buttons</h2>
        <div class="flex flex-wrap gap-3">
          <BaseButton variant="primary">Primary</BaseButton>
          <BaseButton variant="secondary">Secondary</BaseButton>
          <BaseButton variant="ghost">Ghost</BaseButton>
        </div>
      </section>

      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text">Badges</h2>
        <div class="flex flex-wrap gap-3">
          <BaseBadge>Default</BaseBadge>
          <BaseBadge variant="success">Active</BaseBadge>
          <BaseBadge variant="error">Expired</BaseBadge>
        </div>
      </section>

      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text">Card + form</h2>
        <BaseCard class="space-y-4">
          <BaseInput v-model="name" label="Full name" placeholder="Enter your name" />
          <BaseSelect
            v-model="eventType"
            label="Event type"
            placeholder="Choose a type"
            :options="eventTypeOptions"
          />
          <BaseButton variant="primary">Submit</BaseButton>
        </BaseCard>
      </section>

      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text">Modal + drawer</h2>
        <div class="flex flex-wrap gap-3">
          <BaseButton variant="secondary" @click="modalOpen = true">Open modal</BaseButton>
          <BaseButton variant="secondary" @click="drawerOpen = true">Open drawer</BaseButton>
        </div>
        <BaseModal v-model="modalOpen" title="Confirm">
          <p class="text-sm text-text-secondary">This is a modal dialog.</p>
        </BaseModal>
        <BaseDrawer v-model="drawerOpen" title="Filters">
          <p class="text-sm text-text-secondary">This is a side drawer.</p>
        </BaseDrawer>
      </section>

      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text">Tabs</h2>
        <BaseTabs v-model="activeTab" :tabs="tabs">
          <template #upcoming>
            <p class="text-sm text-text-secondary">Upcoming events go here.</p>
          </template>
          <template #past>
            <p class="text-sm text-text-secondary">Past events go here.</p>
          </template>
        </BaseTabs>
      </section>

      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text">Table</h2>
        <BaseTable :columns="orderColumns" :rows="orderRows">
          <template #cell-status="{ row }">
            <BaseBadge :variant="row.status === 'Paid' ? 'success' : 'default'">
              {{ row.status }}
            </BaseBadge>
          </template>
        </BaseTable>
        <BaseTable :columns="orderColumns" :rows="[]" empty-message="No orders yet" />
      </section>

      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text">Toast</h2>
        <div class="flex flex-wrap gap-3">
          <BaseButton variant="secondary" @click="toast.success('Membership renewed')">
            Trigger success
          </BaseButton>
          <BaseButton variant="secondary" @click="toast.error('Payment failed')">
            Trigger error
          </BaseButton>
        </div>
      </section>

      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text">Empty + loading + skeleton</h2>
        <BaseCard>
          <BaseEmptyState
            title="No events yet"
            description="Events you create will show up here."
          />
        </BaseCard>
        <BaseCard>
          <BaseLoadingState label="Loading events…" />
        </BaseCard>
        <BaseCard class="space-y-2">
          <BaseSkeleton height="1.25rem" width="60%" />
          <BaseSkeleton height="1rem" />
          <BaseSkeleton height="1rem" width="80%" />
        </BaseCard>
      </section>
    </div>
  </main>
</template>
