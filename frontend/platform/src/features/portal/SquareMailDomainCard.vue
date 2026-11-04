<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import type { MailDomain } from '@rootsquares/ui/types/platformTypes'
import { errorText } from '@/features/platform/errorText'
import { ApiError, platform } from '@/services/platform'

// The square's own sending domain (W25-R24, ADR 091 and 095, Grove). The owner REQUESTS a domain and the name before the @; rootsquares staff set it up; the owner then adds
// the records at their own domain provider (or sends them to their web person); an hourly job checks and e-mails when it is ready. IT help for a small one-time support fee.
// Every text is in squareSettings.domain* (en.json). Built as drawn in the user's `Sending Domain Redesign.html` (W25-R36, the states 1 to 3): sizes, shapes and wording of
// the design in `ui/src/styles/sending-domain.css` (class `sd`); the page puts it beside the E-mail contact card while nothing is asked, and full width after.
const props = defineProps<{ squareId: string }>()
const emit = defineEmits<{ state: [state: string] }>()
const { t } = useI18n()
const md = ref<MailDomain | null>(null)
const domain = ref('')
const local = ref('hello')
const webPerson = ref('')
const busy = ref('')
const error = ref('')
const note = ref('')
const confirmRemove = ref(false)
const copied = ref('')

const statusKey = computed(() => md.value?.status ?? 'not_started')
const BAD = ['failed', 'partially_failed']
const recordTone = (s: string) => (s === 'verified' ? 'ok' : BAD.includes(s) ? 'bad' : s === 'not_started' ? 'plain' : 'warn')
const preview = computed(() => `${local.value.trim() || 'hello'}@${(md.value?.domain ?? domain.value.trim()) || 'your-domain'}`)
// the pill beside the title: the state in words before anything is read; a failed check says so
const pill = computed<{ tone: string; text: string }>(() => {
  const v = md.value
  if (!v) return { tone: 'plain', text: '' }
  if (v.state === 'verified') return { tone: 'ok', text: t('squareSettings.domainStatus.verified') }
  if (v.state === 'registered') return BAD.includes(statusKey.value) ? { tone: 'bad', text: t(`squareSettings.domainStatus.${statusKey.value}`) } : { tone: 'plain', text: t('squareSettings.domainStateWaiting') }
  return v.state === 'requested' ? { tone: 'warn', text: t('squareSettings.domainStateRequested') } : { tone: 'plain', text: t('squareSettings.domainStateNone') }
})

function apply(v: MailDomain) {
  md.value = v
  if (v.domain) domain.value = v.domain
  local.value = v.local_part || 'hello'
  emit('state', v.allowed ? v.state : 'locked')
}
async function run(what: string, fn: () => Promise<MailDomain>, done = '') {
  busy.value = what; error.value = ''; note.value = ''
  try { apply(await fn()); note.value = done } catch (e) { error.value = e instanceof ApiError && e.code === 'mail_provider_error' ? e.message : errorText(t, e) } finally { busy.value = '' }
}
const load = () => run('load', () => platform.getMailDomain(props.squareId))
const request = () => run('request', () => platform.requestMailDomain(props.squareId, { domain: domain.value.trim(), local_part: local.value.trim() || 'hello' }))
const withdraw = () => run('withdraw', () => platform.withdrawMailDomainRequest(props.squareId))
const saveName = () => run('name', () => platform.setMailFromName(props.squareId, local.value.trim() || 'hello'), t('squareSettings.mailSaved'))
const check = () => run('check', () => platform.checkMailDomain(props.squareId))
const help = () => run('help', () => platform.askMailDomainHelp(props.squareId))
const sendInstructions = () => run('instructions', () => platform.sendMailDomainInstructions(props.squareId, webPerson.value.trim()), t('squareSettings.domainSent'))
async function remove() { confirmRemove.value = false; await run('remove', () => platform.removeMailDomain(props.squareId)); domain.value = '' }
async function copy(text: string, key: string) {
  try { await navigator.clipboard.writeText(text); copied.value = key; setTimeout(() => { if (copied.value === key) copied.value = '' }, 1500) } catch { /* the value is on screen: select it by hand */ }
}
onMounted(load)
</script>

<template>
  <div class="sd sd-card">
    <div class="sd-head">
      <h3 class="sd-eyebrow">{{ t('squareSettings.domainTitle') }}</h3>
      <span v-if="md && md.allowed" class="sd-st" :class="`sd-st--${pill.tone}`">{{ pill.text }}</span>
    </div>
    <p v-if="busy === 'load' && !md" class="sd-help">{{ t('squareSettings.domainLoading') }}</p>

    <!-- not in the package: say what it gives and offer the way up (Billing), and a way to ask (W26-R12) -->
    <template v-else-if="md && !md.allowed">
      <p class="sd-lead">{{ t('squareSettings.domainLocked') }}</p>
      <p class="sd-help">{{ t('squareSettings.domainPitch') }}</p>
      <div class="sd-act" style="justify-content: center"><AppButton icon="card" :to="`/squares/${props.squareId}/billing`">{{ t('siteDomain.upgrade', { package: t('marketing.pricing.launch.grove.name') }) }}</AppButton></div>
      <div class="sd-need" data-testid="domain-talk">
        <span><b>{{ t('siteDomain.talkTitle') }}</b> {{ t('siteDomain.talkBody') }}</span>
        <AppButton icon="send" size="sm" variant="secondary" to="/contact">{{ t('siteDomain.talkButton') }}</AppButton>
      </div>
    </template>

    <template v-else-if="md">
      <!-- 1 · nothing asked yet -->
      <template v-if="md.state === 'none'">
        <p class="sd-lead">{{ t('squareSettings.domainLede') }}</p>
        <form class="sd-form" @submit.prevent="request">
          <AppField v-model="domain" autocomplete="off" :label="t('squareSettings.domainField')" :hint="t('squareSettings.domainHint')" placeholder="mail.yourassociation.org" />
          <div class="sd-pair">
            <AppField v-model="local" autocomplete="off" :label="t('squareSettings.domainLocal')" :suffix="`@${domain.trim() || 'your-domain'}`" />
            <p class="sd-prev">{{ t('squareSettings.domainFrom1') }} <b>{{ preview }}</b>{{ t('squareSettings.domainFrom2') }}</p>
          </div>
          <div class="sd-act"><AppButton icon="plus" type="submit" :loading="busy === 'request'">{{ t(md.auto_approve ? 'squareSettings.domainAdd' : 'squareSettings.domainRequest') }}</AppButton></div>
        </form>
      </template>

      <!-- 2 · asked, waiting for us -->
      <template v-else-if="md.state === 'requested'">
        <p class="sd-lead">{{ t('squareSettings.domainLede') }}</p>
        <div class="sd-cols">
          <div>
            <dl class="sd-dl">
              <dt>{{ t('squareSettings.domainField') }}</dt><dd>{{ md.requested_domain }}</dd>
              <dt>{{ t('squareSettings.domainSendsFrom') }}</dt><dd>{{ md.requested_local || 'hello' }}@{{ md.requested_domain }}</dd>
            </dl>
            <p class="sd-help">{{ t('squareSettings.domainRequestedBody') }}</p>
            <div class="sd-act"><AppButton icon="x" variant="secondary" :loading="busy === 'withdraw'" @click="withdraw">{{ t('squareSettings.domainWithdraw') }}</AppButton></div>
          </div>
          <div v-if="!md.help_requested" class="sd-need" data-testid="domain-help">
            <span><b>{{ t('squareSettings.domainHelpTitle') }}</b> {{ t('squareSettings.domainHelpBody') }}</span>
            <AppButton icon="life" size="sm" variant="secondary" :loading="busy === 'help'" @click="help">{{ t('squareSettings.domainHelpButton') }}</AppButton>
          </div>
          <div v-else class="sd-need" data-testid="domain-help"><span><b>{{ t('squareSettings.domainHelpThanksTitle') }}</b> {{ t('squareSettings.domainHelpThanks') }}</span></div>
        </div>
      </template>

      <!-- 3 · set up by us, waiting for the records -->
      <template v-else-if="md.state === 'registered'">
        <div class="sd-cols">
          <div>
            <p class="sd-lead">{{ t('squareSettings.domainPending') }}</p>
            <p class="sd-strong">{{ t('squareSettings.domainOneStep', { domain: md.domain }) }}</p>
            <form class="sd-form sd-wide" @submit.prevent="sendInstructions">
              <AppField v-model="webPerson" type="email" autocomplete="off" :label="t('squareSettings.domainWeb')" :hint="t('squareSettings.domainWebHint')" placeholder="name@example.org" />
              <div class="sd-act"><AppButton icon="send" type="submit" :loading="busy === 'instructions'">{{ t('squareSettings.domainSend') }}</AppButton></div>
            </form>
          </div>
          <div class="sd-need" data-testid="domain-help">
            <span v-if="md.help_requested"><b>{{ t('squareSettings.domainHelpThanksTitle') }}</b> {{ t('squareSettings.domainHelpThanks') }}</span>
            <template v-else>
              <span><b>{{ t('squareSettings.domainHelpTitle') }}</b> {{ t('squareSettings.domainHelpBody') }}</span>
              <AppButton icon="life" size="sm" variant="secondary" :loading="busy === 'help'" @click="help">{{ t('squareSettings.domainHelpButton') }}</AppButton>
            </template>
          </div>
        </div>
        <details open>
          <summary>{{ t('squareSettings.domainMyself') }}</summary>
          <p class="sd-help sd-steps">{{ t('squareSettings.domainStep1') }} {{ t('squareSettings.domainStep2') }}</p>
          <div class="sd-rec" role="table" :aria-label="t('squareSettings.domainRecords')">
            <div class="sd-rh" role="row"><span>{{ t('squareSettings.domainType') }}</span><span>{{ t('squareSettings.domainName') }}</span><span>{{ t('squareSettings.domainValue') }}</span><span>{{ t('squareSettings.domainStatusCol') }}</span></div>
            <div v-for="(r, i) in md.records" :key="i" class="sd-rr" role="row">
              <span class="sd-ty">{{ r.type }}<small v-if="r.priority != null">{{ t('squareSettings.domainPriority', { n: r.priority }) }}</small></span>
              <div class="sd-cv"><span class="sd-mono">{{ r.name }}</span><button type="button" class="sd-cp" @click="copy(r.name, `n${i}`)"><AppIcon :name="copied === `n${i}` ? 'check' : 'copy'" :size="12" />{{ copied === `n${i}` ? t('squareSettings.domainCopied') : t('squareSettings.domainCopy') }}</button></div>
              <div class="sd-cv"><span class="sd-mono">{{ r.value }}</span><button type="button" class="sd-cp" @click="copy(r.value, `v${i}`)"><AppIcon :name="copied === `v${i}` ? 'check' : 'copy'" :size="12" />{{ copied === `v${i}` ? t('squareSettings.domainCopied') : t('squareSettings.domainCopy') }}</button></div>
              <span><span class="sd-st" :class="`sd-st--${recordTone(r.status)}`">{{ t(`squareSettings.domainStatus.${r.status}`, r.status) }}</span></span>
            </div>
          </div>
        </details>
        <p class="sd-help">{{ t('squareSettings.domainAuto') }}</p>
        <div class="sd-act">
          <AppButton icon="refresh" variant="secondary" :loading="busy === 'check'" @click="check">{{ t('squareSettings.domainCheck') }}</AppButton>
          <AppButton v-if="!confirmRemove" icon="trash" variant="ghost" @click="confirmRemove = true">{{ t('squareSettings.domainRemove') }}</AppButton>
          <template v-else>
            <span class="sd-help">{{ t('squareSettings.domainRemoveAsk') }}</span>
            <AppButton icon="trash" variant="danger" :loading="busy === 'remove'" @click="remove">{{ t('squareSettings.domainRemoveYes') }}</AppButton>
            <AppButton icon="x" variant="secondary" @click="confirmRemove = false">{{ t('squareSettings.domainKeep') }}</AppButton>
          </template>
        </div>
      </template>

      <!-- working -->
      <template v-else>
        <p class="sd-strong">{{ t('squareSettings.domainVerified', { address: md.from_address }) }}</p>
        <form class="sd-form" @submit.prevent="saveName">
          <div class="sd-pair">
            <AppField v-model="local" autocomplete="off" :label="t('squareSettings.domainLocal')" :suffix="`@${md.domain}`" />
            <p class="sd-prev">{{ t('squareSettings.domainFrom1') }} <b>{{ preview }}</b>{{ t('squareSettings.domainFrom2') }}</p>
          </div>
          <div class="sd-act">
            <AppButton icon="check" type="submit" :loading="busy === 'name'">{{ t('squareSettings.domainSaveName') }}</AppButton>
            <AppButton v-if="!confirmRemove" icon="trash" variant="ghost" @click="confirmRemove = true">{{ t('squareSettings.domainRemove') }}</AppButton>
            <template v-else>
              <span class="sd-help">{{ t('squareSettings.domainRemoveAsk') }}</span>
              <AppButton icon="trash" variant="danger" :loading="busy === 'remove'" @click="remove">{{ t('squareSettings.domainRemoveYes') }}</AppButton>
              <AppButton icon="x" variant="secondary" @click="confirmRemove = false">{{ t('squareSettings.domainKeep') }}</AppButton>
            </template>
          </div>
        </form>
      </template>

      <!-- 1 · the offer of help under the form -->
      <div v-if="md.state === 'none'" class="sd-need" data-testid="domain-help">
        <span v-if="md.help_requested"><b>{{ t('squareSettings.domainHelpThanksTitle') }}</b> {{ t('squareSettings.domainHelpThanks') }}</span>
        <template v-else>
          <span><b>{{ t('squareSettings.domainHelpTitle') }}</b> {{ t('squareSettings.domainHelpBody') }}</span>
          <AppButton icon="life" size="sm" variant="secondary" :loading="busy === 'help'" @click="help">{{ t('squareSettings.domainHelpButton') }}</AppButton>
        </template>
      </div>
    </template>

    <p v-if="note" class="sd-help" role="status">{{ note }}</p>
    <p v-if="error" class="sd-error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.sd-pair { display: grid; gap: 6px; max-width: 460px; }
.sd-steps { margin: 8px 0 14px; max-width: 80ch; }
</style>
