<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import UpgradeLink from '../../components/UpgradeLink.vue'
import { squareProfile } from '../../services/squareConfig'
import RichTextEditor from '../../components/ui/RichTextEditor.vue'
import {
  fetchMessageOptions,
  fetchMessage,
  fetchMessageRecipients,
  createMessage,
  updateMessage,
  deleteMessage,
  sendTestMessage,
  sendMessage,
  unscheduleMessage,
  previewAudience,
  MessageValidationError,
  type AdminMessage,
  type AudiencePreview,
  type MessageKind,
  type MessageOptions,
  type MessageRecipientRow,
} from '../../services/messagesApi'
import { formatDateTime, fromDatetimeLocalValue } from '../../utils/date'
import { useToast } from '../../composables/useToast'

// Compose a message to a group (Messages module). The audience is a rule, not a list: it is worked out when the message goes out.
const toast = useToast()
const route = useRoute()
const router = useRouter() as ReturnType<typeof useRouter> | undefined
const messageId = computed(() => (route.params.id ? Number(route.params.id) : null))

const loading = ref(true)
const options = ref<MessageOptions | null>(null)
const message = ref<AdminMessage | null>(null)
const saving = ref(false)
const errors = ref<Record<string, string>>({})

const form = ref({ kind: 'update' as MessageKind, subject: '', body_html: '', audienceType: 'members', params: {} as Record<string, string | number> })
const editable = computed(() => !message.value || message.value.status === 'draft')

const audience = computed(() => options.value?.audiences.find((a) => a.key === form.value.audienceType) ?? null)
// A newsletter (the subscribers) goes out only from the square's own verified sending domain (ADR 091); until then say so and keep Send off (W26-R18). The server refuses it as well.
const newsletterBlocked = computed(() => form.value.audienceType === 'subscribers' && !squareProfile.ownMailDomain)
const audienceChoices = computed(() => (options.value?.audiences ?? []).map((a) => ({ value: a.key, label: a.label })))
const eventChoices = computed(() => [{ value: '', label: 'Choose an event' }, ...(options.value?.events ?? []).map((e) => ({ value: String(e.id), label: e.title }))])
const typeChoices = computed(() => [{ value: '', label: 'Any type' }, ...(options.value?.membership_types ?? []).map((t) => ({ value: t, label: t }))])
const statusChoices = computed(() => [{ value: '', label: 'Any status' }, ...(options.value?.membership_statuses ?? []).map((s) => ({ value: s, label: s }))])

function audiencePayload() {
  const params: Record<string, string | number> = {}
  for (const p of audience.value?.params ?? []) {
    const value = form.value.params[p.name]
    if (value !== undefined && value !== '') params[p.name] = p.type === 'event' ? Number(value) : value
  }
  return { type: form.value.audienceType, params }
}

const preview = ref<AudiencePreview | null>(null)
const previewError = ref('')
let previewTimer: ReturnType<typeof setTimeout> | undefined
function schedulePreview() {
  clearTimeout(previewTimer)
  previewTimer = setTimeout(async () => {
    preview.value = null
    previewError.value = ''
    try {
      preview.value = await previewAudience(audiencePayload(), form.value.kind)
    } catch (e) {
      previewError.value = e instanceof MessageValidationError ? (e.errors.audience ?? '') : ''
    }
  }, 300)
}
watch(() => [form.value.audienceType, form.value.params, form.value.kind], schedulePreview, { deep: true })

function applyMessage(m: AdminMessage) {
  message.value = m
  form.value = { kind: m.kind, subject: m.subject, body_html: m.body_html, audienceType: m.audience.type, params: { ...m.audience.params } }
}

onMounted(async () => {
  try {
    options.value = await fetchMessageOptions()
    if (messageId.value) {
      applyMessage(await fetchMessage(messageId.value))
      await loadRecipients()
    } else {
      // ?audience=subscribers (the Newsletters tab) presets the audience; an unknown or switched-off one is ignored
      const wanted = String(route.query?.audience ?? '')
      const preset = options.value.audiences.find((a) => a.key === wanted) ?? options.value.audiences[0]
      if (preset) form.value.audienceType = preset.key
    }
    schedulePreview()
  } catch {
    toast.error('Could not load this page')
  } finally {
    loading.value = false
  }
})

function payload() {
  return { kind: form.value.kind, subject: form.value.subject, body_html: form.value.body_html, audience: audiencePayload() }
}

async function save(): Promise<boolean> {
  saving.value = true
  errors.value = {}
  try {
    if (message.value) {
      applyMessage(await updateMessage(message.value.id, payload()))
    } else {
      const created = await createMessage(payload())
      applyMessage(created)
      void router?.replace(`/admin/messages/${created.id}`)
    }
    return true
  } catch (e) {
    if (e instanceof MessageValidationError) errors.value = e.errors
    else toast.error('Could not save')
    return false
  } finally {
    saving.value = false
  }
}

async function saveClicked() {
  if (await save()) toast.success('Saved')
}

const testing = ref(false)
async function sendTest() {
  if (!(await save()) || !message.value) return
  testing.value = true
  try {
    const result = await sendTestMessage(message.value.id)
    toast.success(`A test was sent to ${result.sent_to}`)
  } catch {
    toast.error('Could not send the test')
  } finally {
    testing.value = false
  }
}

const confirmOpen = ref(false)
const scheduleAt = ref('')
const sending = ref(false)
async function openConfirm() {
  if (!(await save())) return
  confirmOpen.value = true
}
async function confirmSend(scheduled: boolean) {
  if (!message.value) return
  sending.value = true
  errors.value = {}
  try {
    const when = scheduled && scheduleAt.value ? fromDatetimeLocalValue(scheduleAt.value) : undefined
    if (scheduled && !when) {
      errors.value = { scheduled_for: 'Choose a date and time.' }
      return
    }
    applyMessage(await sendMessage(message.value.id, when))
    confirmOpen.value = false
    toast.success(scheduled ? 'Scheduled' : 'Sending started')
    await loadRecipients()
  } catch (e) {
    if (e instanceof MessageValidationError) errors.value = e.errors
    else toast.error(e instanceof Error ? e.message : 'Could not send')
  } finally {
    sending.value = false
  }
}

async function unschedule() {
  if (!message.value) return
  try {
    applyMessage(await unscheduleMessage(message.value.id))
  } catch {
    toast.error('Could not cancel the schedule')
  }
}

async function remove() {
  if (!message.value) return
  try {
    const newsletter = message.value.audience.type === 'subscribers'
    await deleteMessage(message.value.id)
    void router?.push(newsletter ? '/admin/newsletter/issues' : '/admin/messages')
  } catch {
    toast.error('Could not delete')
  }
}

const recipients = ref<MessageRecipientRow[]>([])
const recipientStatus = ref('')
const recipientStatusChoices = [
  { value: '', label: 'Everyone' },
  { value: 'sent', label: 'Sent' },
  { value: 'failed', label: 'Failed' },
  { value: 'skipped', label: 'Opted out' },
  { value: 'queued', label: 'Waiting' },
]
async function loadRecipients() {
  if (!message.value || message.value.status === 'draft') return
  try {
    recipients.value = (await fetchMessageRecipients(message.value.id, recipientStatus.value)).items
  } catch {
    toast.error('Could not load the people list')
  }
}
watch(recipientStatus, loadRecipients)

const STATUS_LABEL: Record<string, string> = { draft: 'Draft', scheduled: 'Scheduled', sending: 'Sending', sent: 'Sent' }
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Messages</span>
          <h1 class="ds-display ds-display-s">{{ message ? message.subject || 'Message' : 'New message' }}</h1>
        </div>
        <div style="display: flex; gap: var(--ds-space-2); align-items: center">
          <span v-if="message" class="ds-badge ds-badge-neutral">{{ STATUS_LABEL[message.status] }}</span>
          <BaseButton type="button" variant="secondary" size="sm" to="/admin/messages">Back</BaseButton>
        </div>
      </div>
      <hr class="ds-section-line" />

      <BaseLoadingState v-if="loading" label="Loading…" />
      <template v-else>
        <div v-if="message && message.status === 'scheduled'" class="ds-alert ds-alert-info">
          <div>Goes out on {{ formatDateTime(message.scheduled_for!) }}. <BaseButton type="button" variant="ghost" size="sm" class="unschedule" @click="unschedule">Cancel the schedule</BaseButton></div>
        </div>
        <div v-else-if="message && message.status !== 'draft'" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-2)">
          <p class="ds-body">
            <strong>{{ message.sent_count }}</strong> sent<span v-if="message.failed_count">, <strong>{{ message.failed_count }}</strong> failed</span><span v-if="message.skipped_count">, <strong>{{ message.skipped_count }}</strong> skipped (opted out)</span>
            of {{ message.recipients_total }} people.
          </p>
          <p v-if="message.status === 'sending'" class="ds-meta">Sending. Reload this page to see the progress.</p>
        </div>

        <fieldset class="ds-card" :disabled="!editable" style="display: flex; flex-direction: column; gap: var(--ds-space-4); border: 1px solid var(--ds-border, currentColor)">
          <div class="ds-field" role="radiogroup" aria-label="Type of message">
            <span class="ds-field-label">Type</span>
            <label class="ds-checkbox" style="align-items: flex-start">
              <input v-model="form.kind" type="radio" value="update" name="msg-kind" class="kind-update" />
              <span><strong>News</strong><span class="ds-meta" style="display: block">News and invitations from the association. Every e-mail has an unsubscribe link and people who opted out are skipped.</span></span>
            </label>
            <label class="ds-checkbox" style="align-items: flex-start">
              <input v-model="form.kind" type="radio" value="service" name="msg-kind" class="kind-service" />
              <span><strong>Service</strong><span class="ds-meta" style="display: block">A practical notice about something the person booked, bought or joined (a change of venue, a payment due). No unsubscribe; only use it for that.</span></span>
            </label>
            <span v-if="errors.kind" class="ds-field-error-text">{{ errors.kind }}</span>
          </div>

          <div class="ds-field">
            <span class="ds-field-label">Who gets it</span>
            <BaseSelect v-model="form.audienceType" :options="audienceChoices" aria-label="Audience" @update:model-value="form.params = {}" />
            <span v-if="audience" class="ds-field-hint">{{ audience.description }}</span>
            <template v-for="p in audience?.params ?? []" :key="p.name">
              <label v-if="p.type === 'emails'" class="ds-field">
                <span class="ds-field-label">{{ p.label }}</span>
                <span class="ds-textarea-control"><textarea v-model="form.params[p.name] as string" rows="3" class="ds-textarea audience-emails" placeholder="One per line, or separated by commas"></textarea></span>
              </label>
              <label v-else class="ds-field">
                <span class="ds-field-label">{{ p.label }}</span>
                <BaseSelect
                  :model-value="String(form.params[p.name] ?? '')"
                  :options="p.type === 'event' ? eventChoices : p.type === 'membership_type' ? typeChoices : statusChoices"
                  :aria-label="p.label"
                  @update:model-value="(v) => (form.params = { ...form.params, [p.name]: String(v) })"
                />
              </label>
            </template>
            <span v-if="errors.audience || previewError" class="ds-field-error-text">{{ errors.audience || previewError }}</span>
            <p v-if="preview" class="ds-meta audience-preview">
              Goes to <strong>{{ preview.will_receive }}</strong> {{ preview.will_receive === 1 ? 'person' : 'people' }}<span v-if="preview.skipped"> ({{ preview.skipped }} opted out and skipped)</span>.
            </p>
          </div>

          <label class="ds-field">
            <span class="ds-field-label">Subject</span>
            <span class="ds-field-control"><input v-model="form.subject" type="text" maxlength="200" class="ds-field-input message-subject" /></span>
            <span v-if="errors.subject" class="ds-field-error-text">{{ errors.subject }}</span>
          </label>
          <RichTextEditor v-model="form.body_html" label="Message" />
          <span v-if="errors.body_html" class="ds-field-error-text">{{ errors.body_html }}</span>
          <p class="ds-caption">You can write <code v-text="'{{name}}'"></code> to put each person's name in the subject or the text.</p>
        </fieldset>

        <div v-if="editable && newsletterBlocked" class="ds-alert ds-alert-info newsletter-blocked">
          <div>
            A newsletter is sent only from your own sending domain, and yours is not set up or not verified yet. You can write and save it now.
            <UpgradeLink text="Ask the owner to set up the own sending domain on rootsquares (the square's Settings) and wait until it is verified." button="Owner: open rootsquares" />
          </div>
        </div>

        <div v-if="editable" style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap">
          <BaseButton type="button" variant="secondary" size="md" class="save-message" :disabled="saving" @click="saveClicked">Save draft</BaseButton>
          <BaseButton type="button" variant="secondary" size="md" class="send-test" :disabled="saving || testing" @click="sendTest">Send a test to me</BaseButton>
          <BaseButton type="button" variant="primary" size="md" class="open-send" :disabled="saving || newsletterBlocked" @click="openConfirm">Send…</BaseButton>
          <BaseButton v-if="message" type="button" variant="ghost" size="md" class="delete-message" @click="remove">Delete draft</BaseButton>
        </div>

        <section v-if="message && message.status !== 'draft'" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <div style="display: flex; justify-content: space-between; align-items: center; gap: var(--ds-space-3)">
            <h2 class="ds-title">People</h2>
            <BaseSelect v-model="recipientStatus" :options="recipientStatusChoices" aria-label="Filter people" size="sm" />
          </div>
          <p v-if="recipients.length === 0" class="ds-meta">Nobody in this list.</p>
          <table v-else class="ds-table">
            <thead><tr><th>Name</th><th>E-mail</th><th>Status</th></tr></thead>
            <tbody>
              <tr v-for="r in recipients" :key="r.id"><td>{{ r.name || '—' }}</td><td>{{ r.email }}</td><td>{{ r.status }}</td></tr>
            </tbody>
          </table>
        </section>
      </template>
    </div>

    <BaseModal v-model="confirmOpen" title="Send this message?">
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <p class="ds-body">It goes to <strong>{{ preview?.will_receive ?? 0 }}</strong> {{ preview?.will_receive === 1 ? 'person' : 'people' }}. It cannot be taken back once sent.</p>
        <label class="ds-field">
          <span class="ds-field-label">Or send it later</span>
          <span class="ds-field-control"><input v-model="scheduleAt" type="datetime-local" class="ds-field-input schedule-at" /></span>
          <span v-if="errors.scheduled_for" class="ds-field-error-text">{{ errors.scheduled_for }}</span>
        </label>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2); flex-wrap: wrap">
          <BaseButton type="button" variant="ghost" @click="confirmOpen = false">Cancel</BaseButton>
          <BaseButton type="button" variant="secondary" class="confirm-schedule" :disabled="sending || !scheduleAt" @click="confirmSend(true)">Schedule</BaseButton>
          <BaseButton type="button" variant="primary" class="confirm-send" :disabled="sending" @click="confirmSend(false)">Send now</BaseButton>
        </div>
      </div>
    </BaseModal>
  </div>
</template>
