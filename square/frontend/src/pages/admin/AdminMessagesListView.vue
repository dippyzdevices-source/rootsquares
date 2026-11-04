<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import {
  fetchMessages,
  fetchSuppressions,
  addSuppressions,
  removeSuppression,
  MessageValidationError,
  type AdminMessage,
  type Suppression,
} from '../../services/messagesApi'
import { fetchAdminSettings, updateAdminSettings, ValidationError } from '../../services/adminSettingsApi'
import { formatDateTime } from '../../utils/date'
import { useToast } from '../../composables/useToast'

const toast = useToast()
const router = useRouter() as ReturnType<typeof useRouter> | undefined

const items = ref<AdminMessage[]>([])
const total = ref(0)
const page = ref(1)
const perPage = 25
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / perPage)))
const loading = ref(true)

const STATUS_LABEL: Record<string, string> = { draft: 'Draft', scheduled: 'Scheduled', sending: 'Sending', sent: 'Sent' }
const tone = (s: string) => (s === 'sent' ? 'ds-badge-success' : s === 'draft' ? 'ds-badge-neutral' : 'ds-badge-warning')
const KIND_LABEL: Record<string, string> = { update: 'News', service: 'Service' }

async function load() {
  loading.value = true
  try {
    const result = await fetchMessages(page.value)
    items.value = result.items
    total.value = result.total
  } catch {
    toast.error('Could not load messages')
  } finally {
    loading.value = false
  }
}
watch(page, load)
onMounted(load)

// The sentence at the foot of each kind of message (the square's settings; empty = the standard wording). The unsubscribe link of a News message is always added.
const footers = ref({ message_footer_update: '', message_footer_service: '' })
const footerErrors = ref<Record<string, string>>({})
const savingFooters = ref(false)
onMounted(async () => {
  try {
    const s = await fetchAdminSettings()
    footers.value = { message_footer_update: s.message_footer_update ?? '', message_footer_service: s.message_footer_service ?? '' }
  } catch {
    toast.error('Could not load the footer wording')
  }
})
async function saveFooters() {
  savingFooters.value = true
  footerErrors.value = {}
  try {
    await updateAdminSettings({ ...footers.value })
    toast.success('Saved')
  } catch (e) {
    if (e instanceof ValidationError) footerErrors.value = e.errors
    else toast.error('Could not save')
  } finally {
    savingFooters.value = false
  }
}

function open(event: MouseEvent, message: AdminMessage) {
  if ((event.target as HTMLElement).closest('a, button')) return
  void router?.push(`/admin/messages/${message.id}`)
}

// The do-not-contact list: people who opted out of news messages (one list for every audience).
const suppressions = ref<Suppression[]>([])
const newAddresses = ref('')
const suppressionError = ref('')
async function loadSuppressions() {
  try {
    suppressions.value = (await fetchSuppressions()).items
  } catch {
    toast.error('Could not load the do-not-contact list')
  }
}
async function addOptOut() {
  suppressionError.value = ''
  try {
    const { added } = await addSuppressions(newAddresses.value)
    toast.success(added === 1 ? '1 address added' : `${added} addresses added`)
    newAddresses.value = ''
    await loadSuppressions()
  } catch (e) {
    if (e instanceof MessageValidationError) suppressionError.value = e.errors.emails ?? 'Could not add'
    else toast.error('Could not add')
  }
}
async function removeOptOut(row: Suppression) {
  try {
    await removeSuppression(row.id)
    await loadSuppressions()
  } catch {
    toast.error('Could not remove')
  }
}
onMounted(loadSuppressions)
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
          <h1 class="ds-display ds-display-s">Messages</h1>
        </div>
        <div style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap">
          <BaseButton type="button" variant="secondary" size="sm" to="/admin/messages/reminders">Reminders</BaseButton>
          <BaseButton type="button" variant="primary" size="sm" to="/admin/messages/new" class="new-message">New message</BaseButton>
        </div>
      </div>
      <p class="ds-body">Write to a group: members, the ticket holders of an event, volunteers, donors or subscribers. <strong>News</strong> messages can be opted out of; <strong>Service</strong> messages are practical notices about something a person booked or bought.</p>

      <hr class="ds-section-line" />

      <BaseLoadingState v-if="loading" label="Loading messages…" />
      <div v-else-if="items.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)"><p class="ds-meta">No messages yet.</p></div>
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead><tr><th>Subject</th><th>Type</th><th data-align="right">People</th><th>Status</th><th>When</th></tr></thead>
            <tbody>
              <tr v-for="m in items" :key="m.id" class="ds-row-clickable" @click="open($event, m)">
                <td data-emphasis>{{ m.subject }}<div v-if="m.source !== 'manual'" class="ds-caption">Automatic reminder</div></td>
                <td>{{ KIND_LABEL[m.kind] ?? m.kind }}</td>
                <td data-align="right">{{ m.status === 'draft' ? '—' : `${m.sent_count} of ${m.recipients_total - m.skipped_count}` }}</td>
                <td><span class="ds-badge" :class="tone(m.status)">{{ STATUS_LABEL[m.status] ?? m.status }}</span></td>
                <td>{{ m.status === 'scheduled' && m.scheduled_for ? formatDateTime(m.scheduled_for) : m.sent_at ? formatDateTime(m.sent_at) : formatDateTime(m.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <PaginationBar v-model:page="page" :total-pages="totalPages" :total="total" />

      <section class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <h2 class="ds-title">Do-not-contact list</h2>
        <p class="ds-meta">People who unsubscribed from news messages. They are skipped in every audience. Add an address here if someone asks you to stop writing to them.</p>
        <div style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap; align-items: flex-start">
          <label class="ds-field" style="flex: 1 1 280px">
            <span class="ds-field-control"><input v-model="newAddresses" type="text" class="ds-field-input optout-input" placeholder="name@example.com" aria-label="Addresses to add" @keyup.enter="addOptOut" /></span>
            <span v-if="suppressionError" class="ds-field-error-text">{{ suppressionError }}</span>
          </label>
          <BaseButton type="button" variant="secondary" size="sm" class="optout-add" @click="addOptOut">Add</BaseButton>
        </div>
        <p v-if="suppressions.length === 0" class="ds-meta">Nobody has opted out.</p>
        <ul v-else style="list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--ds-space-1)">
          <li v-for="row in suppressions" :key="row.id" style="display: flex; justify-content: space-between; gap: var(--ds-space-3)">
            <span class="ds-body">{{ row.email }}</span>
            <BaseButton type="button" variant="ghost" size="sm" @click="removeOptOut(row)">Remove</BaseButton>
          </li>
        </ul>
      </section>

      <section class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <h2 class="ds-title">Footer of your messages</h2>
        <p class="ds-meta">The sentence at the bottom of every message. Leave a box empty to use the standard wording. The unsubscribe link is always added to a News message.</p>
        <label class="ds-field">
          <span class="ds-field-label">News messages</span>
          <span class="ds-field-control"><textarea v-model="footers.message_footer_update" rows="2" maxlength="400" class="ds-field-input footer-update" placeholder="You receive this because you are in our contact list." /></span>
          <span v-if="footerErrors.message_footer_update" class="ds-field-error-text">{{ footerErrors.message_footer_update }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Service messages</span>
          <span class="ds-field-control"><textarea v-model="footers.message_footer_service" rows="2" maxlength="400" class="ds-field-input footer-service" placeholder="This is a service message about something you booked, bought or joined." /></span>
          <span v-if="footerErrors.message_footer_service" class="ds-field-error-text">{{ footerErrors.message_footer_service }}</span>
        </label>
        <div><BaseButton type="button" variant="primary" size="sm" class="save-footers" :disabled="savingFooters" @click="saveFooters">{{ savingFooters ? 'Saving…' : 'Save' }}</BaseButton></div>
      </section>
    </div>
  </div>
</template>
