<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import RichTextEditor from '../../components/ui/RichTextEditor.vue'
import {
  fetchMessageOptions,
  fetchRules,
  createRule,
  updateRule,
  deleteRule,
  MessageValidationError,
  type MessageRule,
  type Trigger,
} from '../../services/messagesApi'
import { useToast } from '../../composables/useToast'
import { availableReminderSuggestions, groupLabel } from '../../services/starterSuggestions'
import { featureEnabled, GROVE_NOTE } from '../../services/features'
import UpgradeLink from '../../components/UpgradeLink.vue'

// Automatic reminders: "N days before X, tell the people it concerns". Each one is a Service message (no unsubscribe), sent once per event or date.
const toast = useToast()
const unlocked = featureEnabled('message_reminders') // the package decides (W14-R25); the list stays readable
const loading = ref(true)
const rules = ref<MessageRule[]>([])
const triggers = ref<Trigger[]>([])
const triggerChoices = computed(() => triggers.value.map((t) => ({ value: t.key, label: t.label })))

const modalOpen = ref(false)
const editing = ref<MessageRule | null>(null)
const saving = ref(false)
const errors = ref<Record<string, string>>({})
const form = ref({ name: '', trigger: '', offset_days: 1, send_hour: 9, subject: '', body_html: '' })
const placeholders = computed(() => triggers.value.find((t) => t.key === form.value.trigger)?.placeholders ?? [])

const hourChoices = Array.from({ length: 24 }, (_, h) => ({ value: String(h), label: `${String(h).padStart(2, '0')}:00` }))
const label = (key: string) => triggers.value.find((t) => t.key === key)?.label ?? key

async function load() {
  loading.value = true
  try {
    const [options, list] = await Promise.all([fetchMessageOptions(), fetchRules()])
    triggers.value = options.triggers
    rules.value = list.items
  } catch {
    toast.error('Could not load reminders')
  } finally {
    loading.value = false
  }
}
onMounted(load)

function openNew() {
  editing.value = null
  errors.value = {}
  form.value = { name: '', trigger: triggers.value[0]?.key ?? '', offset_days: 1, send_hour: 9, subject: '', body_html: '' }
  modalOpen.value = true
}
function openEdit(rule: MessageRule) {
  editing.value = rule
  errors.value = {}
  form.value = { name: rule.name, trigger: rule.trigger, offset_days: rule.offset_days, send_hour: rule.send_hour, subject: rule.subject, body_html: rule.body_html }
  modalOpen.value = true
}

async function save() {
  saving.value = true
  errors.value = {}
  try {
    const payload = { ...form.value, offset_days: Number(form.value.offset_days), send_hour: Number(form.value.send_hour) }
    if (editing.value) await updateRule(editing.value.id, payload)
    else await createRule(payload)
    modalOpen.value = false
    toast.success('Saved')
    await load()
  } catch (e) {
    if (e instanceof MessageValidationError) errors.value = e.errors
    else toast.error('Could not save')
  } finally {
    saving.value = false
  }
}

// A square with no reminders yet is offered the ones that usually fit its kind of group (starterSuggestions.ts). Nothing is made until the owner says so,
// and each one can be edited, turned off or deleted afterwards.
const suggestions = computed(() => (rules.value.length === 0 ? availableReminderSuggestions().filter((s) => triggers.value.some((t) => t.key === s.trigger)) : []))
const addingSuggestions = ref(false)
async function addSuggestions() {
  addingSuggestions.value = true
  try {
    for (const s of suggestions.value) await createRule(s)
    toast.success('Reminders added. You can edit or turn them off any time.')
    await load()
  } catch {
    toast.error('Could not add the suggested reminders')
  } finally {
    addingSuggestions.value = false
  }
}

async function toggle(rule: MessageRule) {
  try {
    await updateRule(rule.id, { enabled: !rule.enabled })
    await load()
  } catch {
    toast.error('Could not change this reminder')
  }
}

async function remove(rule: MessageRule) {
  try {
    await deleteRule(rule.id)
    await load()
  } catch {
    toast.error('Could not delete this reminder')
  }
}
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Messages</span>
          <h1 class="ds-display ds-display-s">Reminders</h1>
        </div>
        <div style="display: flex; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="secondary" size="sm" to="/admin/messages">Back</BaseButton>
          <BaseButton type="button" variant="primary" size="sm" class="new-rule" :disabled="!unlocked" @click="openNew">New reminder</BaseButton>
        </div>
      </div>
      <hr class="ds-section-line" />
      <p class="ds-body">A reminder is written once and sent by itself, for example "the day before an event, to its ticket holders". Each person gets it once. It is a service message: it only goes to the people it concerns.</p>

      <div v-if="!unlocked" class="ds-alert ds-alert-info feature-locked"><div>Automatic reminders are not part of this package. {{ GROVE_NOTE }} {{ rules.length ? 'Yours are kept but not sent.' : '' }}</div><UpgradeLink /></div>

      <section v-if="!loading && suggestions.length && unlocked" class="ds-card suggested-reminders" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <h2 class="ds-title">Start with these{{ groupLabel() ? ` (for a ${groupLabel()})` : '' }}</h2>
        <ul style="margin: 0; padding-left: var(--ds-space-5)">
          <li v-for="s in suggestions" :key="s.trigger"><strong>{{ s.name }}</strong><span class="ds-meta" style="display: block">{{ s.subject }}</span></li>
        </ul>
        <div><BaseButton type="button" variant="primary" size="sm" class="add-suggested" :disabled="addingSuggestions" @click="addSuggestions">Add these reminders</BaseButton></div>
      </section>

      <BaseLoadingState v-if="loading" label="Loading reminders…" />
      <div v-else-if="rules.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)"><p class="ds-meta">No reminders yet.</p></div>
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead><tr><th>Reminder</th><th>When</th><th>Status</th><th></th></tr></thead>
            <tbody>
              <tr v-for="rule in rules" :key="rule.id">
                <td data-emphasis>{{ rule.name }}<div class="ds-caption">{{ rule.subject }}</div></td>
                <td>{{ rule.offset_days }} {{ rule.offset_days === 1 ? 'day' : 'days' }} before, at {{ String(rule.send_hour).padStart(2, '0') }}:00<div class="ds-caption">{{ label(rule.trigger) }}</div></td>
                <td><span class="ds-badge" :class="rule.enabled ? 'ds-badge-success' : 'ds-badge-neutral'">{{ rule.enabled ? 'On' : 'Off' }}</span></td>
                <td data-align="right">
                  <div style="display: flex; gap: var(--ds-space-2); justify-content: flex-end">
                    <BaseButton type="button" variant="secondary" size="sm" class="edit-rule" :disabled="!unlocked" @click="openEdit(rule)">Edit</BaseButton>
                    <BaseButton type="button" variant="ghost" size="sm" class="toggle-rule" :disabled="!unlocked" @click="toggle(rule)">{{ rule.enabled ? 'Turn off' : 'Turn on' }}</BaseButton>
                    <BaseButton type="button" variant="ghost" size="sm" class="delete-rule" @click="remove(rule)">Delete</BaseButton>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <BaseModal v-model="modalOpen" :title="editing ? 'Edit reminder' : 'New reminder'">
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <label class="ds-field">
          <span class="ds-field-label">Name (only you see it)</span>
          <span class="ds-field-control"><input v-model="form.name" type="text" maxlength="120" class="ds-field-input rule-name" /></span>
          <span v-if="errors.name" class="ds-field-error-text">{{ errors.name }}</span>
        </label>
        <div class="ds-field">
          <span class="ds-field-label">Send</span>
          <BaseSelect v-model="form.trigger" :options="triggerChoices" aria-label="Reminder type" />
          <span v-if="errors.trigger" class="ds-field-error-text">{{ errors.trigger }}</span>
        </div>
        <div style="display: flex; gap: var(--ds-space-4); flex-wrap: wrap">
          <label class="ds-field">
            <span class="ds-field-label">Days before</span>
            <span class="ds-field-control"><input v-model="form.offset_days" type="number" min="0" max="365" class="ds-field-input rule-days" /></span>
            <span v-if="errors.offset_days" class="ds-field-error-text">{{ errors.offset_days }}</span>
          </label>
          <div class="ds-field">
            <span class="ds-field-label">At (the square's time)</span>
            <BaseSelect :model-value="String(form.send_hour)" :options="hourChoices" aria-label="Hour" @update:model-value="(v) => (form.send_hour = Number(v))" />
          </div>
        </div>
        <label class="ds-field">
          <span class="ds-field-label">Subject</span>
          <span class="ds-field-control"><input v-model="form.subject" type="text" maxlength="200" class="ds-field-input rule-subject" /></span>
          <span v-if="errors.subject" class="ds-field-error-text">{{ errors.subject }}</span>
        </label>
        <RichTextEditor v-model="form.body_html" label="Text" />
        <span v-if="errors.body_html" class="ds-field-error-text">{{ errors.body_html }}</span>
        <p v-if="placeholders.length" class="ds-caption">You can use: <code v-for="p in placeholders" :key="p" style="margin-right: var(--ds-space-2)" v-text="'{{' + p + '}}'"></code></p>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" @click="modalOpen = false">Cancel</BaseButton>
          <BaseButton type="button" variant="primary" class="save-rule" :disabled="saving" @click="save">Save</BaseButton>
        </div>
      </div>
    </BaseModal>
  </div>
</template>
