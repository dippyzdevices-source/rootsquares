<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import type { SiteDomain } from '@rootsquares/ui/types/platformTypes'
import { ApiError } from '@rootsquares/ui/types/platformTypes'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/errorText'
import { adminApi as platform } from '@/adminApi'

// A square's own website domain, for staff (W26-R5, ADR 098): the owner's request waits here. Staff add the domain as a custom domain on the square site in the host
// (Render) BY HAND, then press Activate: from then on the square is served on it and the owner is told by e-mail. Turn down tells the owner why not. After activation
// the sign-in project must trust the new address: `flask sync-square-auth <slug>` (guide 40). The card uses the sending-domain card's classes (sd-*), the card itself is oc-card.
const props = defineProps<{ squareId: string }>()
const { t } = useI18n()
const { date } = useFormat()
const sd = ref<SiteDomain | null>(null)
const wanted = ref('')
const note = ref('')
const busy = ref('')
const error = ref('')
const confirmRemove = ref(false)

function apply(v: SiteDomain) {
  sd.value = v
  wanted.value = v.requested_domain ?? v.domain ?? ''
}
async function run(what: string, fn: () => Promise<SiteDomain>) {
  busy.value = what; error.value = ''
  try { apply(await fn()) } catch (e) { error.value = e instanceof ApiError && e.code === 'site_domain_host_error' ? e.message : errorText(t, e) } finally { busy.value = '' }
}
const load = () => run('load', () => platform.getSiteDomain(props.squareId))
const activate = () => run('activate', () => platform.activateSiteDomain(props.squareId, wanted.value.trim()))
const check = () => run('check', () => platform.checkSiteDomain(props.squareId))
const reject = () => run('reject', () => platform.rejectSiteDomain(props.squareId, note.value.trim()))
const remove = async () => { await run('remove', () => platform.removeSiteDomain(props.squareId)); confirmRemove.value = false }
onMounted(load)
</script>

<template>
  <section id="site-domain" class="oc-card sd sd-oc" data-testid="owner-site-domain">
    <header class="sd-hd">
      <h3 class="sd-eyebrow">{{ t('own.siteDomain.title') }}</h3>
      <span v-if="sd && sd.allowed" class="sd-st" :class="`sd-st--${sd.state === 'active' ? 'ok' : sd.state === 'requested' ? 'warn' : 'plain'}`">{{ t(`own.siteDomain.state.${sd.state}`) }}</span>
      <span v-if="sd && sd.allowed && sd.help_requested" class="sd-st sd-st--warn">{{ t('own.siteDomain.helpAsked') }}</span>
    </header>
    <div v-if="sd" class="sd-bd">
      <p v-if="!sd.allowed" class="sd-lead">{{ t('own.siteDomain.notGrove') }}</p>
      <template v-else>
        <p v-if="sd.help_requested" class="sd-help">{{ t('own.siteDomain.helpAskedNote') }}</p>
        <p v-if="sd.state === 'none'" class="sd-lead">{{ t('own.siteDomain.none', { target: sd.target }) }}</p>

        <!-- requested -->
        <template v-if="sd.state === 'requested'">
          <p class="sd-lead">{{ t('own.siteDomain.requestedLine', { when: sd.requested_at ? date(sd.requested_at, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '' }) }}</p>
          <p v-if="sd.render !== 'off'" class="sd-help">{{ t('own.siteDomain.stepAuto') }}</p>
          <ol v-else class="sd-help" style="margin: 0 0 12px; padding-left: 18px">
            <li>{{ t('own.siteDomain.step1', { domain: wanted || sd.requested_domain }) }}</li>
            <li>{{ t('own.siteDomain.step2') }}</li>
          </ol>
          <p v-if="sd.render !== 'off'" class="sd-help">{{ t(`own.siteDomain.render.${sd.render}`) }}</p>
          <p class="sd-help">{{ t(`own.siteDomain.dns.${sd.dns}`, { target: sd.target }) }}</p>
          <div class="sd-fields"><AppField v-model="wanted" autocomplete="off" :label="t('own.siteDomain.domain')" /></div>
          <div class="sd-act"><AppButton icon="check" :loading="busy === 'activate'" @click="activate">{{ t('own.siteDomain.activate') }}</AppButton></div>
          <hr class="sd-rule">
          <div class="sd-form sd-wide">
            <AppField v-model="note" autocomplete="off" :label="t('own.siteDomain.note')" :hint="t('own.siteDomain.noteHint')" />
            <div class="sd-act"><AppButton icon="trash" variant="secondary" :loading="busy === 'reject'" @click="reject">{{ t('own.siteDomain.reject') }}</AppButton></div>
          </div>
        </template>

        <!-- active -->
        <template v-if="sd.state === 'active'">
          <dl class="sd-dl">
            <dt>{{ t('own.siteDomain.domain') }}</dt><dd>{{ sd.domain }}</dd>
            <dt>{{ t('own.siteDomain.defaultAddress') }}</dt><dd>{{ sd.default_domain }}</dd>
            <dt>{{ t('own.siteDomain.dnsLabel') }}</dt><dd>{{ t(`own.siteDomain.dns.${sd.dns}`, { target: sd.target }) }}</dd>
            <dt>{{ t('own.siteDomain.renderLabel') }}</dt><dd>{{ t(`own.siteDomain.render.${sd.render}`) }}</dd>
          </dl>
          <p v-if="sd.render !== 'off'" class="sd-help">{{ t('own.siteDomain.removeAuto') }}</p>
          <p class="sd-help">{{ t('own.siteDomain.signin', { slug: sd.default_domain.split('.')[0] }) }}</p>
          <div class="sd-act">
            <AppButton icon="refresh" variant="secondary" :loading="busy === 'check'" @click="check">{{ t('own.siteDomain.check') }}</AppButton>
            <AppButton v-if="!confirmRemove" icon="trash" variant="danger" @click="confirmRemove = true">{{ t('own.siteDomain.remove') }}</AppButton>
            <template v-else>
              <span class="sd-help">{{ t('own.siteDomain.removeAsk') }}</span>
              <AppButton icon="trash" variant="danger" :loading="busy === 'remove'" @click="remove">{{ t('own.siteDomain.removeYes') }}</AppButton>
              <AppButton icon="x" variant="secondary" @click="confirmRemove = false">{{ t('own.siteDomain.keep') }}</AppButton>
            </template>
          </div>
        </template>
      </template>
    </div>
    <div v-else class="sd-bd"><p class="sd-help">{{ t('own.siteDomain.loading') }}</p></div>
    <p v-if="error" class="sd-error sd-bd" role="alert">{{ error }}</p>
  </section>
</template>
