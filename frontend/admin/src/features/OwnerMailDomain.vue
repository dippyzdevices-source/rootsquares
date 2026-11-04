<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import type { MailDomain } from '@rootsquares/ui/types/platformTypes'
import { ApiError } from '@rootsquares/ui/types/platformTypes'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/errorText'
import { adminApi as platform } from '@/adminApi'

// A square's own sending domain, for staff (ADR 091 and 095): the owner's request waits here; Set up registers the domain at Resend and e-mails the owner the next step;
// Turn down tells the owner why not. The card also shows the state after that (records, status) and lets staff check or remove the domain.
// Built as drawn in the user's `Sending Domain Redesign.html` (W25-R36, the states 5 and 6): the header bar with the title and the state, then the body, in the sizes and
// wording of `ui/src/styles/sending-domain.css` (class `sd`), the card itself is the console's oc-card.
const props = defineProps<{ squareId: string }>()
const { t } = useI18n()
const { date } = useFormat()
const md = ref<MailDomain | null>(null)
const wanted = ref('')
const local = ref('')
const note = ref('')
const busy = ref('')
const error = ref('')

const BAD = ['failed', 'partially_failed']
const tone = (s: string) => (s === 'verified' ? 'ok' : BAD.includes(s) ? 'bad' : s === 'not_started' ? 'plain' : 'warn')
// what a record is for, in words (the same four records Resend asks for)
const purpose = (r: { type: string; name: string }) => (r.type === 'MX' ? 'bounce' : r.type === 'CNAME' ? 'tracking' : r.name.startsWith('send') ? 'spf' : 'dkim')

function apply(v: MailDomain) {
  md.value = v
  wanted.value = v.requested_domain ?? v.domain ?? ''
  local.value = v.requested_local ?? v.local_part
}
async function run(what: string, fn: () => Promise<MailDomain>) {
  busy.value = what; error.value = ''
  try { apply(await fn()) } catch (e) { error.value = e instanceof ApiError && (e.code === 'mail_provider_error' || e.code === 'mail_domain_not_ready') ? e.message : errorText(t, e) } finally { busy.value = '' }
}
const load = () => run('load', () => platform.getMailDomain(props.squareId))
const approve = () => run('approve', () => platform.approveMailDomain(props.squareId, { domain: wanted.value.trim(), local_part: local.value.trim() }))
const reject = () => run('reject', () => platform.rejectMailDomain(props.squareId, note.value.trim()))
const check = () => run('check', () => platform.checkMailDomain(props.squareId))
const confirmRemove = ref(false)
const remove = async () => { await run('remove', () => platform.removeMailDomain(props.squareId)); confirmRemove.value = false }
onMounted(load)
</script>

<template>
  <section id="mail-domain" class="oc-card sd sd-oc" data-testid="owner-mail-domain">
    <header class="sd-hd">
      <h3 class="sd-eyebrow">{{ t('own.mailDomain.title') }}</h3>
      <template v-if="md && md.allowed">
        <span class="sd-st" :class="`sd-st--${md.state === 'verified' ? 'ok' : md.state === 'requested' ? 'warn' : 'plain'}`">{{ t(`own.mailDomain.state.${md.state}`) }}</span>
        <span v-if="md.help_requested" class="sd-st sd-st--warn">{{ t('own.mailDomain.helpAsked') }}</span>
      </template>
    </header>
    <div v-if="md" class="sd-bd">
      <p v-if="!md.allowed" class="sd-lead">{{ t('own.mailDomain.notGrove') }}</p>
      <template v-else>
        <p v-if="!md.available" class="sd-error">{{ t('own.mailDomain.noKey') }}</p>
        <p v-if="md.help_requested" class="sd-help">{{ t('own.mailDomain.helpAskedNote') }}</p>
        <p v-if="md.auto_approve" class="sd-help">{{ t('own.mailDomain.autoOn') }}</p>
        <p v-if="md.state === 'none'" class="sd-lead">{{ t('own.mailDomain.none') }}</p>

        <!-- 5 · requested -->
        <template v-if="md.state === 'requested'">
          <p class="sd-lead">{{ t('own.mailDomain.requestedLine', { when: md.requested_at ? date(md.requested_at, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '' }) }}</p>
          <div class="sd-fields">
            <AppField v-model="wanted" autocomplete="off" :label="t('own.mailDomain.domain')" />
            <AppField v-model="local" autocomplete="off" :label="t('own.mailDomain.local')" :suffix="`@${wanted.trim() || 'your-domain'}`" />
          </div>
          <div class="sd-act"><AppButton icon="check" :loading="busy === 'approve'" :disabled="!md.available" @click="approve">{{ t('own.mailDomain.approve') }}</AppButton></div>
          <hr class="sd-rule">
          <div class="sd-form sd-wide">
            <AppField v-model="note" autocomplete="off" :label="t('own.mailDomain.note')" :hint="t('own.mailDomain.noteHint')" :placeholder="t('own.mailDomain.notePlaceholder')" />
            <div class="sd-act"><AppButton icon="trash" variant="secondary" :loading="busy === 'reject'" @click="reject">{{ t('own.mailDomain.reject') }}</AppButton></div>
          </div>
        </template>

        <!-- 6 · set up (or working) -->
        <template v-if="md.state === 'registered' || md.state === 'verified'">
          <dl class="sd-dl">
            <dt>{{ t('own.mailDomain.domain') }}</dt><dd>{{ md.domain }}</dd>
            <dt>{{ t('own.mailDomain.sendsFrom') }}</dt><dd>{{ md.local_part }}@{{ md.domain }}</dd>
            <dt>{{ t('own.mailDomain.statusLabel') }}</dt><dd>{{ t(`own.mailDomain.status.${md.status ?? 'not_started'}`, md.status ?? '') }}</dd>
          </dl>
          <div v-if="md.records.length" class="sd-rec sd-rec--staff" role="table">
            <div class="sd-rh" role="row"><span>{{ t('own.mailDomain.colType') }}</span><span>{{ t('own.mailDomain.colName') }}</span><span>{{ t('own.mailDomain.colFor') }}</span><span>{{ t('own.mailDomain.statusLabel') }}</span></div>
            <div v-for="(r, i) in md.records" :key="i" class="sd-rr" role="row">
              <span class="sd-ty">{{ r.type }}<small v-if="r.priority != null">{{ t('own.mailDomain.priority', { n: r.priority }) }}</small></span>
              <span class="sd-mono">{{ r.name }}</span>
              <span class="sd-help">{{ t(`own.mailDomain.purpose.${purpose(r)}`) }}</span>
              <span><span class="sd-st" :class="`sd-st--${tone(r.status)}`">{{ t(`own.mailDomain.status.${r.status}`, r.status) }}</span></span>
            </div>
          </div>
          <div class="sd-act">
            <AppButton icon="refresh" variant="secondary" :loading="busy === 'check'" :disabled="!md.available" @click="check">{{ t('own.mailDomain.check') }}</AppButton>
            <AppButton v-if="!confirmRemove" icon="trash" variant="danger" :disabled="!md.available" @click="confirmRemove = true">{{ t('own.mailDomain.remove') }}</AppButton>
            <template v-else>
              <span class="sd-help">{{ t('own.mailDomain.removeAsk') }}</span>
              <AppButton icon="trash" variant="danger" :loading="busy === 'remove'" @click="remove">{{ t('own.mailDomain.removeYes') }}</AppButton>
              <AppButton icon="x" variant="secondary" @click="confirmRemove = false">{{ t('own.mailDomain.keep') }}</AppButton>
            </template>
          </div>
          <p class="sd-help">{{ t('own.mailDomain.autoCheck') }}</p>
        </template>
      </template>
    </div>
    <div v-else class="sd-bd"><p class="sd-help">{{ t('own.mailDomain.loading') }}</p></div>
    <p v-if="error" class="sd-error sd-bd" role="alert">{{ error }}</p>
  </section>
</template>
