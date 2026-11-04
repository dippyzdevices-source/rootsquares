<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import { useEventFilterOptions } from '../../composables/useEventFilterOptions'
import { useToast } from '../../composables/useToast'
import { countBuyers, messageBuyers, MessageInvalidError, MessageRefusedError, type BuyersCount } from '../../services/adminEventPassApi'

// A message to everyone who bought tickets for an event (doors open at 7, a change of room, ...). One e-mail per buyer; the addresses are never shown to each other.
const toast = useToast()
const { eventOptions } = useEventFilterOptions()
const options = computed(() => eventOptions.value.filter((o) => o.value !== ''))
const eventId = ref('')
const subject = ref('')
const message = ref('')
const buyers = ref<BuyersCount | null>(null)
const sending = ref(false)
const errors = ref<Record<string, string>>({})
const notice = ref('')

watch(options, (list) => {
  if (!eventId.value && list.length === 1) eventId.value = list[0]!.value // one event (an Event pass): chosen for you
})

watch(eventId, async (id) => {
  buyers.value = null
  notice.value = ''
  if (!id) return
  try {
    buyers.value = await countBuyers(Number(id))
  } catch {
    buyers.value = null
  }
})

const canSend = computed(() => !!eventId.value && !!subject.value.trim() && !!message.value.trim() && !sending.value && (buyers.value?.count ?? 0) > 0)

async function send() {
  sending.value = true
  errors.value = {}
  notice.value = ''
  try {
    const result = await messageBuyers({ event_id: Number(eventId.value), subject: subject.value.trim(), message: message.value.trim() })
    toast.success(`Sent to ${result.sent} ${result.sent === 1 ? 'person' : 'people'}${result.failed ? ` (${result.failed} could not be reached)` : ''}`)
    subject.value = ''
    message.value = ''
  } catch (e) {
    if (e instanceof MessageInvalidError) errors.value = e.errors
    else if (e instanceof MessageRefusedError) notice.value = e.message
    else toast.error('Could not send the message')
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6); max-width: 640px">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Message ticket buyers</h1>
      </div>
      <hr class="ds-section-line" />
      <p class="ds-meta">Send an e-mail to everyone who has bought a ticket for an event. Each person gets their own e-mail.</p>

      <BaseSelect v-model="eventId" label="Event" placeholder="Choose an event" :options="options" />
      <span v-if="errors.event_id" class="ds-field-error-text">{{ errors.event_id }}</span>
      <p v-if="buyers" class="ds-meta" data-testid="buyers-count">
        {{ buyers.count === 0 ? 'Nobody has bought a ticket for this event yet.' : `This reaches ${buyers.count} ${buyers.count === 1 ? 'person' : 'people'}.` }}
      </p>

      <label class="ds-field">
        <span class="ds-field-label">Subject</span>
        <span class="ds-field-control"><input v-model="subject" type="text" maxlength="150" class="ds-field-input" /></span>
        <span v-if="errors.subject" class="ds-field-error-text">{{ errors.subject }}</span>
      </label>
      <label class="ds-field">
        <span class="ds-field-label">Message</span>
        <span class="ds-textarea-control"><textarea v-model="message" rows="8" maxlength="5000" class="ds-textarea"></textarea></span>
        <span v-if="errors.message" class="ds-field-error-text">{{ errors.message }}</span>
      </label>
      <p v-if="notice" class="ds-field-error-text" role="alert">{{ notice }}</p>

      <div>
        <BaseButton type="button" class="send-message" :disabled="!canSend" @click="send">{{ sending ? 'Sending…' : 'Send to all buyers' }}</BaseButton>
      </div>
    </div>
  </div>
</template>
