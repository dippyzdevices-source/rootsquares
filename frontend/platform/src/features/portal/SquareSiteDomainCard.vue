<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import type { SiteDomain } from '@rootsquares/ui/types/platformTypes'
import CopyField from '@/components/ui/CopyField.vue'
import { errorText } from '@/features/platform/errorText'
import { platform } from '@/services/platform'

// The square's own website domain (W26-R5, ADR 098, Grove). The owner types a domain such as www.theirassociation.org and adds ONE CNAME at their own domain
// provider, pointing at our name (squares.rootsquares.com, the `target`): the host behind it is never shown. rootsquares staff add the domain on the host and
// activate it; the owner is told by e-mail. The page keeps its own card pattern (`oc-card`); every text is in siteDomain.* (platform en.json).
const props = defineProps<{ squareId: string }>()
const { t } = useI18n()
const sd = ref<SiteDomain | null>(null)
const domain = ref('')
const busy = ref('')
const error = ref('')
const confirmRemove = ref(false)

const shown = computed(() => sd.value?.domain ?? sd.value?.requested_domain ?? '')

function apply(v: SiteDomain) { sd.value = v }
async function run(what: string, fn: () => Promise<SiteDomain>) {
  busy.value = what; error.value = ''
  try { apply(await fn()) } catch (e) { error.value = errorText(t, e) } finally { busy.value = '' }
}
const load = () => run('load', () => platform.getSiteDomain(props.squareId))
const request = () => run('request', () => platform.requestSiteDomain(props.squareId, domain.value.trim()))
const withdraw = () => run('withdraw', () => platform.withdrawSiteDomainRequest(props.squareId))
const check = () => run('check', () => platform.checkSiteDomain(props.squareId))
const help = () => run('help', () => platform.askSiteDomainHelp(props.squareId))
async function remove() { confirmRemove.value = false; await run('remove', () => platform.removeSiteDomain(props.squareId)); domain.value = '' }
onMounted(load)
</script>

<template>
  <section class="oc-card" data-testid="site-domain">
    <h3 class="oc-h3">{{ t('portal.domain.custom') }}</h3>
    <div v-if="busy === 'load' && !sd" style="padding: 14px 18px"><p class="oc-mut" style="margin: 0; font-size: var(--text-sm)">{{ t('siteDomain.loading') }}</p></div>

    <!-- not in the package: say what it gives, and offer the way up (the Billing page is where a package is changed) -->
    <div v-else-if="sd && !sd.allowed" class="sd-cols" style="padding: 14px 18px" data-testid="site-domain-locked">
      <div>
        <AppAlert tone="info" :title="t('siteDomain.lockedTitle')">{{ t('siteDomain.locked') }}</AppAlert>
        <p class="oc-mut" style="margin: 0; font-size: var(--text-sm)">{{ t('siteDomain.pitch') }}</p>
        <div style="display: flex; justify-content: center"><AppButton icon="card" :to="`/squares/${props.squareId}/billing`">{{ t('siteDomain.upgrade', { package: t('marketing.pricing.launch.grove.name') }) }}</AppButton></div>
      </div>
      <div class="sd-need" style="padding: 10px 14px; gap: 10px; font-size: var(--text-sm); align-self: center" data-testid="site-domain-talk">
        <span><b>{{ t('siteDomain.talkTitle') }}</b> {{ t('siteDomain.talkBody') }}</span>
        <AppButton icon="send" size="sm" variant="secondary" to="/contact">{{ t('siteDomain.talkButton') }}</AppButton>
      </div>
    </div>

    <template v-else-if="sd">
      <!-- the label rows span the card; below them the instructions on the left and the offer of help on the right (the pattern of the sending-domain card) -->
      <template v-if="sd.state !== 'none'">
        <div class="oc-li"><span class="oc-mut">{{ t('siteDomain.yourDomain') }}</span><span style="word-break: break-all">{{ shown }}</span></div>
        <div class="oc-li">
          <span class="oc-mut">{{ t('siteDomain.state') }}</span>
          <span>{{ sd.state === 'active' ? t('siteDomain.stateActive') : t('siteDomain.stateRequested') }}</span>
        </div>
      </template>
      <div class="sd-cols" style="padding: 14px 18px">
        <!-- 1 · nothing asked yet -->
        <div v-if="sd.state === 'none'">
          <form style="display: grid; gap: 12px" @submit.prevent="request">
            <p class="oc-mut" style="margin: 0; font-size: var(--text-sm)">{{ t('siteDomain.lede', { target: sd.target }) }}</p>
            <AppField v-model="domain" autocomplete="off" :label="t('siteDomain.field')" :hint="t('siteDomain.hint')" placeholder="www.yourassociation.org" />
            <div><AppButton icon="plus" type="submit" :loading="busy === 'request'">{{ t('siteDomain.request') }}</AppButton></div>
          </form>
        </div>

        <!-- 2 · asked, or 3 · active: the one record to add -->
        <div v-else>
          <p class="oc-mut" style="margin: 0; font-size: var(--text-sm)">{{ sd.state === 'active' ? t('siteDomain.activeBody', { address: sd.default_domain }) : t('siteDomain.requestedBody') }}</p>
          <p style="margin: 0; font-size: var(--text-sm)"><b>{{ t('siteDomain.recordTitle') }}</b> {{ t('siteDomain.recordBody', { domain: shown }) }}</p>
          <CopyField :label="t('siteDomain.recordType')" value="CNAME" />
          <CopyField :label="t('siteDomain.recordName')" :value="shown" />
          <CopyField :label="t('siteDomain.recordValue')" :value="sd.target" />
          <p class="oc-mut" style="margin: 0; font-size: var(--text-sm)">{{ t('siteDomain.apexNote') }}</p>
          <AppAlert v-if="sd.dns === 'pointing'" tone="success" :title="t('siteDomain.dnsPointingTitle')">{{ t('siteDomain.dnsPointing') }}</AppAlert>
          <AppAlert v-else-if="sd.dns === 'not_pointing'" tone="warning" :title="t('siteDomain.dnsNotTitle')">{{ t('siteDomain.dnsNot', { target: sd.target }) }}</AppAlert>
          <AppAlert v-else-if="sd.dns === 'unknown'" tone="warning" :title="t('siteDomain.dnsUnknownTitle')">{{ t('siteDomain.dnsUnknown') }}</AppAlert>
          <div style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center">
            <AppButton icon="refresh" variant="secondary" :loading="busy === 'check'" @click="check">{{ t('siteDomain.check') }}</AppButton>
            <AppButton v-if="sd.state === 'requested'" icon="x" variant="secondary" :loading="busy === 'withdraw'" @click="withdraw">{{ t('siteDomain.withdraw') }}</AppButton>
            <AppButton v-else-if="!confirmRemove" icon="trash" variant="ghost" @click="confirmRemove = true">{{ t('siteDomain.remove') }}</AppButton>
            <template v-else>
              <span class="oc-mut">{{ t('siteDomain.removeAsk') }}</span>
              <AppButton icon="trash" variant="danger" :loading="busy === 'remove'" @click="remove">{{ t('siteDomain.removeYes') }}</AppButton>
              <AppButton icon="x" variant="secondary" @click="confirmRemove = false">{{ t('siteDomain.keep') }}</AppButton>
            </template>
          </div>
        </div>

        <!-- the offer of help, with its one-off fee (the same words as the sending-domain card) -->
        <div class="sd-need" style="padding: 10px 14px; gap: 10px; font-size: var(--text-sm); align-self: center" data-testid="site-domain-help">
          <span v-if="sd.help_requested"><b>{{ t('squareSettings.domainHelpThanksTitle') }}</b> {{ t('squareSettings.domainHelpThanks') }}</span>
          <template v-else>
            <span><b>{{ t('squareSettings.domainHelpTitle') }}</b> {{ t('squareSettings.domainHelpBody') }}</span>
            <AppButton icon="life" size="sm" variant="secondary" :loading="busy === 'help'" @click="help">{{ t('squareSettings.domainHelpButton') }}</AppButton>
          </template>
        </div>
      </div>
    </template>

    <div v-if="error" style="padding: 0 18px 14px"><AppAlert tone="danger" :title="t('siteDomain.errorTitle')">{{ error }}</AppAlert></div>
  </section>
</template>
