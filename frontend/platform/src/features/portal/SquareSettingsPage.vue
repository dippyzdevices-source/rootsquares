<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import { errorText } from '@/features/platform/errorText'
import SquareMailDomainCard from './SquareMailDomainCard.vue'
import { platform } from '@/services/platform'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { getTheme } from '@rootsquares/ui/themes'
import SquareLogos from './SquareLogos.vue'
import { useSquare } from './squareContext'
import { scrollToHash } from './scrollToHash'

// Settings (W23-R38), redesigned from the design project's `Square Settings Redesign.html`: the basics in four labelled cards (identity, address, plan,
// region and billing), then the two logos. Read only (editing waits for a backend; MISSING.md), except the E-mail contact card (W25-R9). The name and status are in the frame's header above.
const { t } = useI18n()
const { date } = useFormat()
const { sq, set } = useSquare()
const route = useRoute()
onMounted(() => scrollToHash(route.hash)) // "Needs your attention" links here with #mail-domain (W25-R35)
const regions = new Intl.DisplayNames(['en'], { type: 'region' })
const country = (c: string | null | undefined) => (c ? `${regions.of(c) ?? c} (${c})` : '–')
// The owner's e-mail contact (W25-R9, ADR 093): the only editable field of this page.
const mailEmail = ref('')
const mailBusy = ref(false)
const mailError = ref('')
const mailSaved = ref(false)
const domainState = ref('')
const wideDomain = computed(() => ['requested', 'registered', 'verified'].includes(domainState.value)) // the own sending domain card is full width once a domain is asked for
watch(() => sq.value?.mail_contact_email, (v) => { mailEmail.value = v ?? '' }, { immediate: true })
async function saveMail() {
  if (!sq.value) return
  mailBusy.value = true; mailError.value = ''; mailSaved.value = false
  try { set(await platform.setMailContact(sq.value.id, mailEmail.value.trim() || null)); mailSaved.value = true } catch (e) { mailError.value = errorText(t, e) } finally { mailBusy.value = false }
}
const created = computed(() => (sq.value ? date(sq.value.created_at, { day: 'numeric', month: 'short', year: 'numeric' }) : ''))
</script>

<template>
  <template v-if="sq">
    <div class="bw-hd"><h2 class="bs-h2" style="font-size: 28px">{{ t('portal.nav.settings') }}</h2><p class="bs-mute" style="margin: 0; font-size: var(--text-sm)">{{ t('portal.settings.lede') }}</p></div>

    <section class="st-sec">
      <h2 class="bs-h2 st-h">{{ t('portal.settings.basics') }}</h2>
      <p class="st-sub">{{ t('squareSettings.basicsSub') }}</p>
      <div class="st-grid">
        <div class="st-card">
          <h3>{{ t('squareSettings.identity') }}</h3>
          <div class="st-r"><span>{{ t('portal.settings.name') }}</span><b>{{ sq.name }}</b></div>
          <div class="st-r"><span>{{ t('portal.settings.slug') }}</span><b>{{ sq.slug }}</b></div>
          <div class="st-r"><span>{{ t('portal.settings.theme') }}</span><b>{{ getTheme(sq.theme_id)?.name ?? sq.theme_id }}</b></div>
        </div>
        <div class="st-card">
          <h3>{{ t('squareSettings.address') }}</h3>
          <div class="st-r"><span>{{ t('plat.detail.domain') }}</span><b>{{ sq.domain }}</b></div>
          <div class="st-r">
            <span>{{ t('portal.domain.custom') }}</span>
            <b>
              <template v-if="sq.custom_domain">{{ sq.custom_domain }}</template>
              <template v-else><em>{{ t('squareSettings.notConnected') }}</em><AppButton icon="arrow" class="st-btn" :to="`/squares/${sq.id}/domain`" variant="secondary" size="sm">{{ t('squareSettings.connect') }}</AppButton></template>
            </b>
          </div>
        </div>
        <div class="st-card">
          <h3>{{ t('squareSettings.plan') }}</h3>
          <div class="st-r"><span>{{ t('plat.modules.package') }}</span><b>{{ t(`marketing.pricing.launch.${sq.launch_package}.name`, t('marketing.pricing.running.event.name')) }}</b></div>
          <div class="st-r"><span>{{ t('portal.settings.plan') }}</span><b><span class="st-pill">{{ t(`marketing.pricing.running.${sq.running_plan}.name`) }}</span></b></div>
          <div class="st-r"><span>{{ t('portal.settings.modules') }}</span><b>{{ t('portal.settings.modulesOn', { n: sq.modules.length }) }}<AppButton icon="arrow" class="st-btn" :to="`/squares/${sq.id}/modules`" variant="secondary" size="sm">{{ t('squareSettings.manage') }}</AppButton></b></div>
        </div>
        <div class="st-card">
          <h3>{{ t('squareSettings.region') }}</h3>
          <div class="st-r"><span>{{ t('portal.settings.currency') }}</span><b>{{ sq.currency }}</b></div>
          <div class="st-r"><span>{{ t('portal.settings.billingCountry') }}</span><b>{{ country(sq.billing_country) }}</b></div>
          <div class="st-r"><span>{{ t('portal.settings.phoneCountry') }}</span><b>{{ country(sq.phone_country) }}</b></div>
        </div>
        <!-- E-mail contact and Own sending domain as drawn in `Sending Domain Redesign.html` (W25-R36): side by side while no domain is asked for, the domain card full width after -->
        <div class="sd sd-card st-top" :class="{ 'st-w': wideDomain }">
          <h3 class="sd-eyebrow">{{ t('squareSettings.mailTitle') }}</h3>
          <form class="sd-form" @submit.prevent="saveMail">
            <AppField v-model="mailEmail" type="email" autocomplete="off" :label="t('squareSettings.mailLabel')" :hint="t('squareSettings.mailHint')" :error="mailError" />
            <div class="sd-act"><AppButton icon="check" type="submit" :loading="mailBusy">{{ t('squareSettings.mailSave') }}</AppButton><span v-if="mailSaved" class="sd-help" role="status">{{ t('squareSettings.mailSaved') }}</span></div>
          </form>
        </div>
        <SquareMailDomainCard id="mail-domain" class="st-top" :class="{ 'st-w': wideDomain }" :square-id="sq.id" @state="domainState = $event" />
        <div class="st-card st-w st-created">{{ t('squareSettings.createdOn', { date: created }) }}</div>
      </div>
    </section>

    <SquareLogos />
  </template>
</template>

<style scoped>
/* Tokens only: the design's cream, rust and corners are mapped to the theme (brass), and the shapes come from shape.css. */
.st-sec { display: grid; gap: 0; }
.st-h { font-size: 28px; margin: 12px 0 4px; }
.st-sub { margin: 0 0 14px; color: var(--color-text-muted); font-size: var(--text-sm); }
.st-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.st-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--shape-surface); padding: 16px 20px; }
.st-w { grid-column: 1 / -1; }
.st-card h3 { margin: 0 0 4px; font: 600 10px var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-text-muted); }
.st-r { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 10px 0; border-top: 1px solid var(--color-border); min-height: 44px; font-size: var(--text-sm); }
.st-card h3 + .st-r { border-top: 0; }
.st-r span { color: var(--color-text-muted); }
.st-r b { display: flex; flex-wrap: wrap; justify-content: flex-end; align-items: center; gap: 10px; font-weight: 500; text-align: right; word-break: break-all; }
.st-r em { font-style: normal; color: var(--color-text-muted); opacity: 0.75; }
.st-pill { padding: 2px 12px; border-radius: var(--shape-control); background: var(--color-surface-sunken); font-weight: 500; }
.st-top { align-self: start; }
.st-created { padding-block: 12px; color: var(--color-text-muted); font-size: var(--text-sm); }
/* The small outlined button of the design: capitals, light outline (the same as Copy link on the square page). */
.st-btn.st-btn { padding: 0 12px; border-radius: var(--shape-control); border-color: var(--color-border); background: var(--color-surface); color: var(--color-text); font: 600 10px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; white-space: nowrap; }
.st-btn.st-btn:hover { border-color: var(--color-brass); background: var(--color-surface-sunken); }
@media (max-width: 700px) { .st-grid { grid-template-columns: 1fr; } }
</style>
