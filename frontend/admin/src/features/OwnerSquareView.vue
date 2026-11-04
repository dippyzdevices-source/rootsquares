<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import AppTabs from '@rootsquares/ui/components/AppTabs.vue'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import OcPill from '@rootsquares/ui/components/OcPill.vue'
import SectionCard from '@rootsquares/ui/components/SectionCard.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { getTheme } from '@rootsquares/ui/themes'
import SquareHistory from './SquareHistory.vue'
import SupportCard from './SupportCard.vue'
import OwnerCustomPackage from './OwnerCustomPackage.vue'
import OwnerMailDomain from './OwnerMailDomain.vue'
import OwnerSiteDomain from './OwnerSiteDomain.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/errorText'
import { type OwnerSquareDetail } from '../adminTypes'
import { adminApi as platform } from '@/adminApi'
import { usd } from '@rootsquares/ui/mock/pricing'

// Owner console, one square (platform admin only): facts, history and the actions that used to need the command line.
// Restyled in W13-R34 from the same blocks as the People list and the person page (OcHead, oc-card, oc-li, OcPill): there is no design of its own for this page.
const { t } = useI18n()
const { date } = useFormat()
const { push } = useToast()
const route = useRoute()
const router = useRouter()
const sq = ref<OwnerSquareDetail | null>(null)
const hasOwnAuth = computed(() => !!sq.value && (!!sq.value.provider_project_ref || sq.value.provider === 'neon')) // a Supabase square has a project ref, a Neon square has only provider 'neon' (W27-R3)
const error = ref('')
const notice = ref('')
const busy = ref('')
const suspendOpen = ref(false)
type OwnerOrder = OwnerSquareDetail['orders'][number]
const refundRow = ref<OwnerOrder | null>(null) // the payment whose refund dialog is open (W13-R31)
const refundMode = ref<'full' | 'partial'>('full')
const refundAmount = ref('')
const confirmSlug = ref('')
type Tab = 'overview' | 'package' | 'actions' | 'payments' | 'history'
const tab = ref<Tab>(route.query.tab === 'package' ? 'package' : route.query.tab === 'actions' ? 'actions' : 'overview') // History grows without end, so it has its own tab; Package is opened from a prospect with ?tab=package&prospect=<id>; "Needs attention" opens ?tab=actions#mail-domain (W25-R33)
const tabs = computed(() => [{ id: 'overview', label: t('own.square.tabOverview') }, { id: 'package', label: t('own.square.tabPackage') }, { id: 'actions', label: t('own.square.actions') }, { id: 'payments', label: t('own.square.tabPayments') }, { id: 'history', label: t('own.square.timeline') }])
const force = ref(false)
const TONE = { ready: 'ok', provisioning: 'warn', failed: 'bad' } as const
const themeName = (id: string) => getTheme(id)?.name ?? id
const regions = new Intl.DisplayNames(['en'], { type: 'region' })
const country = (code?: string | null) => (code ? `${regions.of(code) ?? code} (${code})` : '–')
let timer: ReturnType<typeof setInterval> | undefined

async function load() {
  try { sq.value = await platform.ownerSquare(String(route.params.id)); error.value = '' } catch (e) { error.value = errorText(t, e); stop(); return }
  if (sq.value.status === 'provisioning' && !timer) timer = setInterval(load, 2000)
  if (sq.value.status !== 'provisioning') stop()
  if (!scrolled) { scrolled = true; scrollToHash() }
}
// A link like /squares/<id>?tab=actions#mail-domain scrolls to that card once it has been drawn (a card may fetch its own data first: try for two seconds).
let scrolled = false
function scrollToHash(tries = 20) {
  const wanted = route.hash.slice(1)
  if (!wanted) return
  const el = document.getElementById(wanted)
  if (el) el.scrollIntoView({ block: 'start' })
  else if (tries > 0) setTimeout(() => scrollToHash(tries - 1), 100)
}
function stop() { if (timer) { clearInterval(timer); timer = undefined } }
onMounted(load)
onBeforeUnmount(stop)

async function run(name: string, fn: () => Promise<string | void>) {
  busy.value = name; notice.value = ''; error.value = ''
  try { notice.value = (await fn()) ?? ''; await load() } catch (e) { error.value = errorText(t, e) }
  busy.value = ''
}
const id = () => sq.value?.id ?? ''
const retry = () => run('retry', async () => { await platform.retrySquare(id()) })
const check = () => run('check', async () => { const r = await platform.checkSquare(id()); return r.ok ? t('own.square.checkOk', { n: r.admins ?? 0 }) : t('own.square.checkFail') })
const sync = () => run('sync', async () => { await platform.syncSquareAuth(id()); return t('own.square.synced') })
const google = (on: boolean) => run('google', async () => { await platform.setSquareGoogle(id(), on, true) })
const suspend = (on: boolean) => { suspendOpen.value = false; return run('suspend', async () => { await platform.suspendSquare(id(), on) }) }
const refundLeft = computed(() => refundRow.value?.refundable_minor ?? 0)
const refundMinor = computed(() => Math.round(parseFloat(refundAmount.value.replace(',', '.')) * 100))
const refundValid = computed(() => refundMode.value === 'full' || (Number.isFinite(refundMinor.value) && refundMinor.value >= 1 && refundMinor.value <= refundLeft.value))
const refundText = computed(() => (refundMode.value === 'partial' ? t('own.square.refundTextPartial') : refundRow.value?.kind === 'event_pass' ? t('own.square.refundTextEvent') : t('own.square.refundText')))
function openRefund(o: OwnerOrder) { refundRow.value = o; refundMode.value = (o.refunded_minor ?? 0) > 0 ? 'partial' : 'full'; refundAmount.value = '' }
const refund = () => {
  const row = refundRow.value
  const partial = refundMode.value === 'partial'
  const minor = refundMinor.value
  refundRow.value = null
  if (!row) return
  return run('refund', async () => {
    await platform.refundOrder(row.id, partial ? minor : undefined)
    return partial ? t('own.square.refundedPartial', { amount: usd(minor) }) : row.kind === 'event_pass' ? t('own.square.refundedEvent') : t('own.square.refunded')
  })
}
const orderKind = (k: string) => t(`own.square.orderKind.${k}`)

async function remove() {
  if (!sq.value) return
  busy.value = 'delete'; error.value = ''
  try { await platform.deleteSquare(sq.value.id, confirmSlug.value, force.value); await router.push('/squares') } catch (e) { error.value = errorText(t, e) }
  busy.value = ''
}
async function copy(text: string | null) { if (text) try { await navigator.clipboard.writeText(text); push(t('own.square.copied'), 'success') } catch { /* clipboard unavailable */ } }
const when = (iso: string) => date(iso, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
</script>

<template>
  <div class="oc-back">
    <nav :aria-label="t('own.square.crumb')"><ol class="rs-crumbs"><li><RouterLink class="oc-crumb" to="/squares">{{ t('own.square.back') }}</RouterLink><span aria-hidden="true">/</span></li><li v-if="sq" aria-current="page">{{ sq.name }}</li></ol></nav>
    <AppButton to="/squares" variant="secondary" size="sm" icon="chevron-left">{{ t('own.square.backBtn') }}</AppButton>
  </div>
  <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
  <AppAlert v-if="notice" tone="success">{{ notice }}</AppAlert>
  <template v-if="sq">
    <header class="sd-hd">
      <span class="sd-av" aria-hidden="true">{{ sq.name.trim().charAt(0).toUpperCase() }}</span>
      <div class="sd-t">
        <h1>{{ sq.name }} <OcPill :tone="sq.archived_at ? 'mute' : sq.awaiting_payment ? 'warn' : TONE[sq.status]">{{ sq.archived_at ? t('own.square.archived') : sq.awaiting_payment ? t('plat.status.awaiting') : t(`plat.owner.st.${sq.status}`) }}</OcPill></h1>
        <p>{{ sq.domain }} · {{ t('own.square.createdOn', { when: when(sq.created_at) }) }}{{ sq.archived_at ? ` · ${t('own.square.archivedOn', { date: when(sq.archived_at) })}` : sq.suspended_at ? ` · ${t('own.square.suspendedSince', { date: when(sq.suspended_at) })}` : '' }}</p>
      </div>
      <a v-if="sq.status === 'ready' && !sq.archived_at" class="rs-btn" :href="'https://' + sq.domain" target="_blank" rel="noopener"><AppIcon name="external" />{{ t('own.square.openSquare') }}</a>
    </header>
    <AppAlert v-if="sq.error" tone="danger">{{ sq.error }}</AppAlert>
    <AppTabs v-model="tab" class="sd-tabs" :tabs="tabs" :label="t('own.square.tabsLabel')">
      <div v-if="tab === 'overview'" class="sd-grid">
        <section class="sd-card">
          <h2>{{ t('own.square.groupOwnership') }}</h2>
          <dl>
            <div class="sd-r"><dt>{{ t('own.square.organisation') }}</dt><dd>{{ sq.organization_name }}</dd></div>
            <div class="sd-r"><dt>{{ t('own.square.owner') }}</dt><dd><a v-if="sq.owner_email" :href="`mailto:${sq.owner_email}`">{{ sq.owner_email }}</a><template v-else>–</template></dd></div>
            <div class="sd-r"><dt>{{ t('own.square.theme') }}</dt><dd>{{ themeName(sq.theme_id) }}</dd></div>
          </dl>
        </section>
        <section class="sd-card">
          <h2>{{ t('own.square.groupAddress') }}</h2>
          <dl>
            <div class="sd-r"><dt>{{ t('own.square.subdomain') }}</dt><dd>{{ sq.slug }}</dd></div>
            <div class="sd-r"><dt>{{ t('own.square.publicUrl') }}</dt><dd><a :href="`https://${sq.domain}`" target="_blank" rel="noopener">{{ sq.domain }}</a><button type="button" class="sd-cp" :title="t('own.square.copy')" :aria-label="t('own.square.copy')" @click="copy(`https://${sq.domain}`)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 0 1 2-2h9" /></svg></button></dd></div>
          </dl>
        </section>
        <section class="sd-card sd-w">
          <h2>{{ t('own.square.groupHosting') }}</h2>
          <dl>
            <div class="sd-r"><dt>{{ t('own.square.provider') }}</dt><dd>{{ sq.provider ?? '–' }}</dd></div>
            <div class="sd-r"><dt>{{ t('own.square.project') }}</dt><dd>
              <span class="sd-mono">{{ sq.provider_project_ref ?? '–' }}</span>
              <button v-if="sq.provider_project_ref" type="button" class="sd-cp" :title="t('own.square.copyProject')" :aria-label="t('own.square.copyProject')" @click="copy(sq.provider_project_ref)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 0 1 2-2h9" /></svg></button>
              <AppButton v-if="sq.dashboard_url" icon="external" variant="secondary" size="sm" :href="sq.dashboard_url" external>{{ t('own.square.dashboard') }}</AppButton>
            </dd></div>
          </dl>
        </section>
        <section class="sd-card sd-w">
          <h2>{{ t('own.square.groupRegion') }}</h2>
          <div class="sd-chips">
            <span><small>{{ t('own.square.country') }}</small>{{ country(sq.billing_country) }}</span>
            <span><small>{{ t('own.square.currency') }}</small>{{ sq.currency }}</span>
            <span><small>{{ t('own.square.phoneCountry') }}</small>{{ sq.phone_country }}</span>
          </div>
        </section>
        <SupportCard class="sd-w" :square-id="sq.id" :slug="sq.slug" />
      </div>
      <OwnerCustomPackage v-else-if="tab === 'package'" :square="sq" :prospect-id="typeof route.query.prospect === 'string' ? route.query.prospect : undefined" @saved="load" />
      <div v-else-if="tab === 'actions'" style="display: grid; gap: 16px">
        <section class="oc-card">
          <h3 class="oc-h3">{{ t('own.square.actions') }}</h3>
          <div class="oc-acts">
            <AppButton v-if="sq.status === 'failed'" icon="refresh" :loading="busy === 'retry'" @click="retry">{{ t('own.square.retry') }}</AppButton>
            <template v-if="sq.status === 'ready'">
              <AppButton icon="refresh" variant="secondary" :loading="busy === 'check'" @click="check">{{ t('own.square.check') }}</AppButton>
              <AppButton v-if="hasOwnAuth" icon="refresh" variant="secondary" :loading="busy === 'sync'" @click="sync">{{ t('own.square.sync') }}</AppButton>
              <template v-if="hasOwnAuth">
                <AppButton v-if="sq.google_login !== 'enabled'" icon="refresh" variant="secondary" :loading="busy === 'google'" @click="google(true)">{{ t('own.square.googleOn') }}</AppButton>
                <AppButton v-else icon="refresh" variant="secondary" :loading="busy === 'google'" @click="google(false)">{{ t('own.square.googleOff') }}</AppButton>
                <AppButton icon="copy" variant="secondary" @click="copy(sq.auth_callback_url)">{{ t('own.square.copyCallback') }}</AppButton>
              </template>
              <AppButton v-if="!sq.suspended_at" icon="ban" variant="danger" @click="suspendOpen = true">{{ t('own.square.suspend') }}</AppButton>
            </template>
            <AppButton v-if="sq.suspended_at" icon="circle-check" variant="secondary" :loading="busy === 'suspend'" @click="suspend(false)">{{ t('own.square.unsuspend') }}</AppButton>
          </div>
          <p v-if="sq.status === 'ready' && hasOwnAuth && sq.google_login !== 'enabled'" class="oc-mut" style="margin: 0; padding: 0 12px 12px; font-size: var(--text-xs)">{{ t('own.square.googleNote') }}</p>
        </section>
        <OwnerMailDomain v-if="sq.status === 'ready'" :square-id="sq.id" />
        <OwnerSiteDomain v-if="sq.status === 'ready'" :square-id="sq.id" />
        <SectionCard v-if="sq.status !== 'provisioning'" :title="t('set.danger')" danger>
          <form style="display: grid; gap: 12px; max-width: 480px" @submit.prevent="remove">
            <b style="font-weight: 500; font-size: var(--text-sm)">{{ t('own.square.deleteTitle') }}</b>
            <p class="bs-mute" style="margin: 0">{{ t('own.square.deleteText') }}</p>
            <AppField v-model="confirmSlug" :label="t('own.square.deleteConfirm', { slug: sq.slug })" autocomplete="off" />
            <label class="bs-row" style="gap: 8px"><input v-model="force" type="checkbox" /> {{ t('own.square.deleteForce') }}</label>
            <div><AppButton icon="trash" type="submit" variant="danger" :loading="busy === 'delete'" :disabled="confirmSlug.trim().toLowerCase() !== sq.slug">{{ t('own.square.deleteButton') }}</AppButton></div>
          </form>
        </SectionCard>
      </div>
      <template v-else-if="tab === 'payments'">
        <section v-if="sq.orders.length" class="oc-card" data-testid="owner-payments">
          <h3 class="oc-h3">{{ t('own.square.payments') }}</h3>
          <div v-for="o in sq.orders" :key="o.id" class="oc-li">
            <div>
              <b>{{ orderKind(o.kind) }} · {{ usd(o.amount_minor) }}</b>
              <small>{{ when(o.paid_at ?? o.created_at) }}<template v-if="o.card_last4"> · {{ o.card_brand }} ···· {{ o.card_last4 }}</template></small>
            </div>
            <div class="oc-row">
              <RouterLink v-if="o.status === 'paid' || o.status === 'refunded'" :to="`/squares/${sq.id}/invoice/${o.id}`" class="oc-link" style="font-size: var(--text-sm)">{{ t('portal.invoice.link') }}</RouterLink>
              <OcPill :tone="o.status === 'paid' ? 'ok' : o.status === 'pending' ? 'warn' : o.status === 'refunded' ? 'info' : 'mute'">{{ t(`portal.checkout.states.${o.status}`) }}</OcPill>
              <span v-if="(o.refunded_minor ?? 0) > 0 && o.status !== 'refunded'" class="oc-mut">{{ t('own.square.refundedPart', { amount: usd(o.refunded_minor ?? 0) }) }}</span>
              <AppButton v-if="o.refundable" icon="receipt" variant="danger" size="sm" :loading="busy === 'refund'" @click="openRefund(o)">{{ t('own.square.refund') }}</AppButton>
            </div>
          </div>
          <p class="oc-mut" style="margin: 0; padding: 14px 18px; font-size: var(--text-xs)">{{ t('own.square.refundNote') }}</p>
        </section>
        <p v-else class="oc-mut" style="margin: 0">{{ t('own.square.noPayments') }}</p>
      </template>
      <SquareHistory v-else :square-id="sq.id" />
    </AppTabs>
    <ConfirmDialog v-if="refundRow" :title="t('own.square.refundTitle', { name: sq.name })" :body="refundText" icon="receipt" :verb="t('own.square.refund')" :name="sq.slug" :confirm-disabled="!refundValid" @cancel="refundRow = null" @confirm="refund">
      <div style="display: grid; gap: 10px">
        <label v-if="(refundRow.refunded_minor ?? 0) === 0" class="bs-row" style="gap: 8px"><input v-model="refundMode" type="radio" value="full"> {{ t('own.square.refundFull', { amount: usd(refundRow.amount_minor) }) }}</label>
        <label class="bs-row" style="gap: 8px"><input v-model="refundMode" type="radio" value="partial"> {{ t('own.square.refundPartial') }}</label>
        <div v-if="refundMode === 'partial'" class="rs-field" style="gap: 6px">
          <label class="rs-label" for="refund-amount">{{ t('own.square.refundAmount', { max: usd(refundLeft) }) }}</label>
          <input id="refund-amount" v-model="refundAmount" class="rs-input" inputmode="decimal" autocomplete="off" :aria-invalid="refundAmount && !refundValid ? true : undefined">
        </div>
      </div>
    </ConfirmDialog>
    <ConfirmDialog v-if="suspendOpen" :title="t('own.square.suspendTitle', { name: sq.name })" :body="t('own.square.suspendText')" icon="ban" :verb="t('own.square.suspend')" :name="sq.slug" @cancel="suspendOpen = false" @confirm="suspend(true)" />
  </template>
</template>

<style scoped>
/* Redesign (W23-R24, from the design project's Square Detail Redesign.html), in the console's own tokens. Only the header, the tabs bar and the Overview tab are redesigned. */
.sd-hd { display: flex; flex-wrap: wrap; gap: 18px; align-items: center; margin-bottom: 22px; }
.sd-av { flex: none; display: grid; place-items: center; width: 64px; height: 64px; border-radius: var(--shape-control); background: var(--color-brass-subtle); color: var(--color-brass-text); font: 500 34px var(--font-display); }
.sd-t { flex: 1; min-width: 220px; }
.sd-hd h1 { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin: 0; font: 500 42px / 1.1 var(--font-display); }
.sd-hd h1 .oc-pill { padding: 3px 10px; font: 600 10px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; }
.sd-hd p { margin: 2px 0 0; color: var(--color-text-muted); }
.sd-tabs :deep(.rs-tabs) { gap: 2px; border-bottom: 1px solid var(--color-border); overflow-y: hidden; }
.sd-tabs :deep(.rs-tab) { padding: 10px 16px; border-bottom: 2px solid transparent; margin-bottom: 0; }
.sd-tabs :deep(.rs-tab[aria-selected='true']) { color: var(--color-text); font-weight: 600; border-bottom-color: var(--color-brass); }
.sd-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.sd-card { padding: 16px 20px; border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-surface); }
.sd-w { grid-column: 1 / -1; }
.sd-card h2 { margin: 0 0 6px; color: var(--color-text-muted); font: 600 10px var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; }
.sd-card dl { margin: 0; }
.sd-r { display: flex; justify-content: space-between; gap: 16px; align-items: center; min-height: 44px; padding: 10px 0; border-top: 1px solid var(--color-border); }
.sd-r:first-child { border-top: 0; }
.sd-r dt { color: var(--color-text-muted); }
.sd-r dd { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: flex-end; margin: 0; font-weight: 500; text-align: right; word-break: break-all; }
.sd-mono { font-family: ui-monospace, Menlo, monospace; font-size: 12.5px; }
.sd-cp { flex: none; display: grid; place-items: center; width: 28px; height: 28px; padding: 0; border: 0; border-radius: 50%; background: var(--color-surface-sunken); color: var(--color-text-muted); cursor: pointer; }
.sd-cp:hover { background: var(--color-brass-subtle); color: var(--color-text); }
.sd-chips { display: flex; flex-wrap: wrap; gap: 8px; padding-top: 8px; }
.sd-chips span { padding: 3px 12px; border-radius: var(--shape-control); background: var(--color-surface-sunken); font-size: var(--text-sm); }
.sd-chips small { margin-inline-end: 6px; color: var(--color-text-muted); font-size: 10px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }
@media (max-width: 760px) { .sd-grid { grid-template-columns: 1fr; } }
</style>
