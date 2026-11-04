<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppCheck from '@rootsquares/ui/components/AppCheck.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import OcHead from '@/components/OcHead.vue'
import OcPill from '@rootsquares/ui/components/OcPill.vue'
import StateGate from '@rootsquares/ui/components/StateGate.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/errorText'
import { usd } from '@rootsquares/ui/mock/pricing'
import { type LaunchPackageId, type PlatformVoucher, type VoucherInput } from '@rootsquares/ui/types/platformTypes'
import { type PartnerReport, type PlatformPartner, type VoucherRedemption, type VoucherSettings } from '../adminTypes'
import { adminApi as platform } from '@/adminApi'
import { simulate } from './voucherSim'

// Owner console, Vouchers (W14-R27, redesigned in W19-R35 from the design project's `Vouchers.html`; docs/reference/prices-and-vouchers.md): codes that lower a launch
// package or an Event pass once, and the partners (affiliates) who bring customers. A use is a paid order that carries the voucher. The referral link is the
// platform's address with ?ref=CODE; payouts to partners are made by hand from the report. Beside the lists: how several codes combine, and a play checkout.
const { t } = useI18n()
const { date } = useFormat()
const { push } = useToast()
const vouchers = ref<PlatformVoucher[]>([])
const partners = ref<PlatformPartner[]>([])
const loading = ref(true)
const error = ref('')
const state = computed(() => (loading.value ? 'loading' : error.value ? 'error' : 'default'))
const day = (iso: string | null) => (iso ? date(iso, { day: 'numeric', month: 'short', year: 'numeric' }) : '')

async function load() {
  loading.value = true
  try {
    ;[vouchers.value, partners.value] = await Promise.all([platform.listVouchers(), platform.listPartners()])
    error.value = ''
    if (!played.value) { played.value = true; typed.value = vouchers.value.filter((v) => v.active).slice(0, 1).map((v) => v.code) }
  } catch (e) { error.value = errorText(t, e) }
  loading.value = false
}
onMounted(load)

// How codes combine (W15-R19): a platform setting, so it can change later without code.
const MODES = ['best', 'sequential', 'additive'] as const
const stacking = ref<VoucherSettings>({ mode: 'best', max_codes: 2 })
const savedStack = ref<VoucherSettings>({ mode: 'best', max_codes: 2 })
const stackingBusy = ref(false)
const stackDirty = computed(() => stacking.value.mode !== savedStack.value.mode || stacking.value.max_codes !== savedStack.value.max_codes)
onMounted(async () => { try { stacking.value = await platform.voucherSettings(); savedStack.value = { ...stacking.value } } catch { /* the card keeps its defaults; the page shows its own errors */ } })
async function saveStacking() {
  stackingBusy.value = true
  try {
    savedStack.value = await platform.saveVoucherSettings({ mode: stacking.value.mode, max_codes: stacking.value.max_codes })
    stacking.value = { ...savedStack.value }
    push(t('own.vouchers.stackSaved'), 'success')
  } catch (e) { push(errorText(t, e), 'danger') } finally { stackingBusy.value = false }
}
const bump = (d: number) => { stacking.value = { ...stacking.value, max_codes: Math.min(5, Math.max(1, stacking.value.max_codes + d)) } }

// The play checkout: a price and the codes a customer would type, with the setting above (also when it is not saved yet)
const played = ref(false)
const typed = ref<string[]>([])
const playPrice = ref('100')
const priceMinor = computed(() => { const n = Math.round(parseFloat(playPrice.value.replace(',', '.')) * 100); return Number.isFinite(n) && n > 0 ? n : 0 })
const typedVouchers = computed(() => typed.value.map((c) => vouchers.value.find((v) => v.code === c && v.active)).filter((v): v is PlatformVoucher => !!v))
const sim = computed(() => simulate(priceMinor.value, typedVouchers.value, stacking.value.mode, stacking.value.max_codes))
const addable = computed(() => vouchers.value.filter((v) => v.active && !typed.value.includes(v.code)))

const what = (v: PlatformVoucher) => (v.kind === 'percent' ? `${v.value} %` : usd(v.value))
const tags = (v: PlatformVoucher) => [t(`own.vouchers.scope.${v.applies_to}`), ...(v.packages ?? [])]
const validity = (v: PlatformVoucher) => (v.valid_from || v.valid_until ? `${day(v.valid_from) || '…'} – ${day(v.valid_until) || '…'}` : t('own.vouchers.always'))
const referral = (code: string) => `${window.location.origin}/?ref=${encodeURIComponent(code)}`
async function copyLink(code: string) {
  try { await navigator.clipboard.writeText(referral(code)); push(t('own.vouchers.copied'), 'success') } catch { push(referral(code), 'info') }
}
async function copyCode(code: string) {
  try { await navigator.clipboard.writeText(code); push(t('own.vouchers.codeCopied'), 'success') } catch { push(code, 'info') }
}

// ---- voucher form
interface VForm { code: string; kind: 'percent' | 'fixed'; value: string; applies_to: VoucherInput['applies_to']; packages: Record<LaunchPackageId, boolean>; valid_from: string; valid_until: string; max_uses: string; once_per_org: boolean; new_customers_only: boolean; active: boolean; stackable: boolean; partner_id: string; note: string }
const blank = (): VForm => ({ code: '', kind: 'percent', value: '20', applies_to: 'all', packages: { roots: false, square: false, grove: false, event: false }, valid_from: '', valid_until: '', max_uses: '', once_per_org: true, new_customers_only: false, active: true, stackable: false, partner_id: '', note: '' })
const editing = ref<PlatformVoucher | null>(null)
const form = ref<VForm | null>(null)
const formError = ref('')
const busy = ref(false)
const startsAt = (iso: string | null) => (iso ? iso.slice(0, 10) : '')

function openNew() { editing.value = null; form.value = blank(); formError.value = '' }
function openEdit(v: PlatformVoucher) {
  editing.value = v
  const f = blank()
  Object.assign(f, { code: v.code, kind: v.kind, value: v.kind === 'percent' ? String(v.value) : (v.value / 100).toFixed(2).replace(/\.00$/, ''), applies_to: v.applies_to, valid_from: startsAt(v.valid_from), valid_until: startsAt(v.valid_until), max_uses: v.max_uses ? String(v.max_uses) : '', once_per_org: v.once_per_org, new_customers_only: v.new_customers_only, active: v.active, stackable: v.stackable, partner_id: v.partner_id ?? '', note: v.note ?? '' })
  for (const p of v.packages ?? []) f.packages[p] = true
  form.value = f
  formError.value = ''
}
function toValue(f: VForm): number | null {
  if (f.kind === 'percent') { const n = Number(f.value); return Number.isInteger(n) && n >= 1 && n <= 100 ? n : null }
  const m = /^\s*(\d{1,6})(?:[.,](\d{1,2}))?\s*$/.exec(f.value)
  return m ? Number(m[1]) * 100 + Number((m[2] ?? '').padEnd(2, '0') || 0) : null
}
async function saveVoucher() {
  const f = form.value
  if (!f) return
  const value = toValue(f)
  if (value === null || value < 1) { formError.value = t(f.kind === 'percent' ? 'own.vouchers.badPercent' : 'own.vouchers.badAmount'); return }
  const maxUses = f.max_uses.trim() ? Number(f.max_uses) : null
  if (maxUses !== null && (!Number.isInteger(maxUses) || maxUses < 1)) { formError.value = t('own.vouchers.badUses'); return }
  const packages = (Object.keys(f.packages) as LaunchPackageId[]).filter((p) => f.packages[p] && p !== 'event')
  const input: VoucherInput = {
    code: f.code, kind: f.kind, value, applies_to: f.applies_to, packages: packages.length ? packages : null,
    valid_from: f.valid_from ? `${f.valid_from}T00:00:00Z` : null, valid_until: f.valid_until ? `${f.valid_until}T23:59:59Z` : null,
    max_uses: maxUses, once_per_org: f.once_per_org, new_customers_only: f.new_customers_only, active: f.active, stackable: f.stackable, partner_id: f.partner_id || null, note: f.note.trim() || null,
  }
  busy.value = true
  formError.value = ''
  try {
    if (editing.value) {
      // a field the form emptied is sent in `clear`; the others go as they are
      const clearable = ['packages', 'valid_from', 'valid_until', 'max_uses', 'partner_id', 'note'] as const
      const clear = clearable.filter((k) => input[k] === null)
      const body = Object.fromEntries(Object.entries(input).filter(([, v]) => v !== null))
      await platform.updateVoucher(editing.value.id, { ...(body as Partial<VoucherInput>), clear })
    } else { await platform.createVoucher(input) }
    form.value = null
    push(t('own.vouchers.saved'), 'success')
    await load()
  } catch (e) { formError.value = errorText(t, e) } finally { busy.value = false }
}
async function toggleActive(v: PlatformVoucher) {
  try { await platform.updateVoucher(v.id, { active: !v.active }); await load() } catch (e) { push(errorText(t, e), 'danger') }
}

// ---- redemptions
const redemptionsOf = ref<PlatformVoucher | null>(null)
const redemptions = ref<VoucherRedemption[]>([])
async function openRedemptions(v: PlatformVoucher) {
  redemptionsOf.value = v
  redemptions.value = []
  try { redemptions.value = await platform.voucherRedemptions(v.id) } catch (e) { push(errorText(t, e), 'danger') }
}

// ---- partners
const pForm = ref<{ id: string | null; name: string; email: string; commission: string; active: boolean } | null>(null)
const pError = ref('')
function openPartner(p?: PlatformPartner) { pForm.value = { id: p?.id ?? null, name: p?.name ?? '', email: p?.email ?? '', commission: String(p?.commission_percent ?? 10), active: p?.active ?? true }; pError.value = '' }
async function savePartner() {
  const f = pForm.value
  if (!f) return
  const commission = Number(f.commission)
  if (!f.name.trim() || !Number.isInteger(commission) || commission < 0 || commission > 100) { pError.value = t('own.vouchers.badPartner'); return }
  const input = { name: f.name.trim(), email: f.email.trim() || null, commission_percent: commission, active: f.active }
  busy.value = true
  try {
    await (f.id ? platform.updatePartner(f.id, input) : platform.createPartner(input))
    pForm.value = null
    push(t('own.vouchers.saved'), 'success')
    await load()
  } catch (e) { pError.value = errorText(t, e) } finally { busy.value = false }
}
const report = ref<PartnerReport | null>(null)
async function openReport(p: PlatformPartner) {
  try { report.value = await platform.partnerReport(p.id) } catch (e) { push(errorText(t, e), 'danger') }
}
const partnerChoices = computed(() => [{ value: '', label: t('own.vouchers.noPartner') }, ...partners.value.map((p) => ({ value: p.id, label: p.name }))])
const kindChoices = computed(() => [{ value: 'percent', label: t('own.vouchers.percent') }, { value: 'fixed', label: t('own.vouchers.fixed') }])
const scopeChoices = computed(() => (['all', 'launch', 'event_pass'] as const).map((s) => ({ value: s, label: t(`own.vouchers.scope.${s}`) })))
const used = computed(() => !!editing.value && editing.value.uses > 0)
</script>

<template>
  <OcHead :title="t('own.vouchers.title')" :sub="t('own.vouchers.sub')">
    <button type="button" class="oc-btn oc-btn--g" data-testid="new-partner" @click="openPartner()"><AppIcon name="plus" :size="14" />{{ t('own.vouchers.newPartner') }}</button>
    <button type="button" class="oc-btn" data-testid="new-voucher" @click="openNew"><AppIcon name="plus" :size="14" />{{ t('own.vouchers.newVoucher') }}</button>
  </OcHead>

  <div class="vo-rule">
    <div><b>{{ t('own.vouchers.ruleLowers') }}</b><span>{{ t('own.vouchers.ruleLowersText') }}</span></div>
    <div><b>{{ t('own.vouchers.ruleNever') }}</b><span>{{ t('own.vouchers.ruleNeverText') }}</span></div>
    <div><b>{{ t('own.vouchers.ruleUse') }}</b><span>{{ t('own.vouchers.ruleUseText') }}</span></div>
  </div>

  <StateGate :state="state" :rows="4" empty-title="" empty-text="" @retry="load">
    <div class="vo-grid">
      <div class="vo-main">
        <section class="vo-card" data-testid="codes-card">
          <div class="vo-ch"><h3>{{ t('own.vouchers.codes') }}</h3><span class="vo-n">{{ t('own.vouchers.count', { n: vouchers.length }, vouchers.length) }}</span><span class="vo-sp" /><button type="button" class="oc-btn oc-btn--g" @click="openNew"><AppIcon name="plus" :size="14" />{{ t('own.vouchers.newVoucher') }}</button></div>
          <div v-if="!vouchers.length" class="vo-empty"><div><b>{{ t('own.vouchers.emptyTitle') }}</b>{{ t('own.vouchers.emptyText') }}</div></div>
          <div v-for="v in vouchers" :key="v.id" class="vo-vr" :class="{ off: !v.active }" :data-testid="`voucher-${v.code}`">
            <div class="vo-id">
              <span class="vo-off">{{ what(v) }}</span>
              <div>
                <button type="button" class="vo-code" :title="t('own.vouchers.copyCode')" @click="copyCode(v.code)">{{ v.code }}</button>
                <div class="vo-tags"><span v-for="g in tags(v)" :key="g" class="vo-tg">{{ g }}</span></div>
                <small v-if="v.note" class="oc-mut" style="display: block; margin-top: 4px">{{ v.note }}</small>
              </div>
            </div>
            <div class="vo-meta">
              <div><small>{{ t('own.vouchers.colValid') }}</small>{{ validity(v) }}</div>
              <div><small>{{ t('own.vouchers.colUses') }}</small><b>{{ v.uses }}</b><span v-if="v.max_uses" class="oc-mut"> / {{ v.max_uses }}</span><div class="vo-meter"><i :style="{ width: (v.max_uses ? Math.min(100, (v.uses / v.max_uses) * 100) : 0) + '%' }" /></div></div>
              <div><small>{{ t('own.vouchers.colGiven') }}</small>{{ usd(v.discount_minor) }}</div>
              <div><small>{{ t('own.vouchers.colPartner') }}</small>{{ v.partner_name ?? '—' }}</div>
            </div>
            <div class="vo-acts">
              <button type="button" class="vo-sw" :class="{ on: v.active }" :aria-pressed="v.active" :aria-label="t(v.active ? 'own.vouchers.switchOff' : 'own.vouchers.switchOn')" @click="toggleActive(v)"><span class="vo-tgl" />{{ t(v.active ? 'own.vouchers.on' : 'own.vouchers.off') }}</button>
              <button type="button" class="oc-btn oc-btn--g" @click="openEdit(v)"><AppIcon name="edit" :size="14" />{{ t('own.vouchers.edit') }}</button>
              <button type="button" class="oc-btn oc-btn--g" @click="copyLink(v.code)"><AppIcon name="copy" :size="14" />{{ t('own.vouchers.copyLink') }}</button>
              <button type="button" class="oc-btn oc-btn--g" :disabled="!v.uses" @click="openRedemptions(v)"><AppIcon name="users" :size="14" />{{ t('own.vouchers.uses') }}</button>
            </div>
          </div>
        </section>

        <section class="vo-card" data-testid="partners-card">
          <div class="vo-ch"><h3>{{ t('own.vouchers.partners') }}</h3><span class="vo-sp" /><button type="button" class="oc-btn oc-btn--g" @click="openPartner()"><AppIcon name="plus" :size="14" />{{ t('own.vouchers.newPartner') }}</button></div>
          <div v-if="!partners.length" class="vo-empty"><div><b>{{ t('own.vouchers.noPartnersTitle') }}</b>{{ t('own.vouchers.noPartnersText') }}</div></div>
          <div v-for="p in partners" :key="p.id" class="vo-vr vo-pr">
            <div class="vo-id"><div><b>{{ p.name }}</b><small v-if="p.email" class="oc-mut" style="display: block">{{ p.email }}</small></div></div>
            <div class="vo-meta">
              <div><small>{{ t('own.vouchers.colCommission') }}</small>{{ p.commission_percent }} %</div>
              <div><small>{{ t('own.vouchers.colCodes') }}</small>{{ p.vouchers }} <OcPill v-if="!p.active" tone="warn">{{ t('own.vouchers.off') }}</OcPill></div>
            </div>
            <div class="vo-acts">
              <button type="button" class="oc-btn oc-btn--g" @click="openReport(p)"><AppIcon name="chart" :size="14" />{{ t('own.vouchers.report') }}</button>
              <button type="button" class="oc-btn oc-btn--g" @click="openPartner(p)"><AppIcon name="edit" :size="14" />{{ t('own.vouchers.edit') }}</button>
            </div>
          </div>
        </section>
      </div>

      <div class="vo-side">
        <section class="vo-card" data-testid="stacking-card">
          <div class="vo-ch"><h3>{{ t('own.vouchers.stackTitle') }}</h3></div>
          <div class="vo-pad">
            <p class="oc-mut" style="margin: 0">{{ t('own.vouchers.stackNote') }}</p>
            <button v-for="m in MODES" :key="m" type="button" class="vo-opt" :class="{ on: stacking.mode === m }" :aria-pressed="stacking.mode === m" :data-testid="`stack-mode-${m}`" @click="stacking = { ...stacking, mode: m }">
              <i /><div><b>{{ t(`own.vouchers.stackMode.${m}`) }}</b><small>{{ t(`own.vouchers.stackHint.${m}`) }}</small></div>
            </button>
            <div class="vo-step"><span>{{ t('own.vouchers.stackMax') }}</span><div class="vo-stp"><button type="button" :aria-label="t('own.vouchers.fewer')" @click="bump(-1)">−</button><span data-testid="stack-max">{{ stacking.max_codes }}</span><button type="button" :aria-label="t('own.vouchers.more')" @click="bump(1)">+</button></div></div>
            <div class="vo-save"><button type="button" class="oc-btn" data-testid="stack-save" :disabled="!stackDirty || stackingBusy" @click="saveStacking"><AppIcon name="check" :size="14" />{{ t('own.vouchers.stackSave') }}</button><span class="oc-mut">{{ t(stackDirty ? 'own.vouchers.unsaved' : 'own.vouchers.stackSaved') }}</span></div>
          </div>
        </section>

        <section class="vo-sim" data-testid="play-checkout">
          <h3>{{ t('own.vouchers.simTitle') }}</h3>
          <div class="vo-ln"><span>{{ t('own.vouchers.simPackage') }}</span><span class="vo-price">$<input v-model="playPrice" inputmode="decimal" :aria-label="t('own.vouchers.simPackage')"></span></div>
          <div>
            <div v-for="l in sim.used" :key="l.code" class="vo-ln d"><span class="vo-x">{{ l.code }}<button type="button" class="vo-rm" :aria-label="t('own.vouchers.simRemove')" @click="typed = typed.filter((c) => c !== l.code)">×</button></span><span>−{{ usd(l.off) }}</span></div>
            <div v-for="l in sim.ignored" :key="l.code" class="vo-ln ig"><span class="vo-x">{{ l.code }}<button type="button" class="vo-rm" :aria-label="t('own.vouchers.simRemove')" @click="typed = typed.filter((c) => c !== l.code)">×</button></span><span>{{ t(`own.vouchers.simWhy.${l.why}`) }}</span></div>
            <small v-if="!typed.length">{{ t('own.vouchers.simNone') }}</small>
          </div>
          <div class="vo-tot"><small>{{ t('own.vouchers.simPays') }}</small><b data-testid="play-total">{{ usd(sim.payable) }}</b></div>
          <div v-if="addable.length" class="vo-add"><button v-for="v in addable" :key="v.id" type="button" class="vo-addbtn" @click="typed = [...typed, v.code]"><AppIcon name="arrow" :size="14" />{{ v.code }}</button></div>
          <small>{{ t('own.vouchers.simNote') }}</small>
        </section>
      </div>
    </div>
  </StateGate>

  <ConfirmDialog v-if="form" :title="t(editing ? 'own.vouchers.editVoucher' : 'own.vouchers.newVoucher')" :verb="t('own.vouchers.save')" tone="primary" wide :confirm-disabled="busy" @confirm="saveVoucher" @cancel="form = null">
    <div class="vo-form">
      <AppField v-model="form.code" :label="t('own.vouchers.fCode')" :hint="used ? t('own.vouchers.codeLocked') : t('own.vouchers.fCodeHint')" :disabled="used" autocomplete="off" />
      <AppField v-model="form.kind" as="select" :label="t('own.vouchers.fKind')" :options="kindChoices" />
      <AppField v-model="form.value" :label="t(form.kind === 'percent' ? 'own.vouchers.fPercent' : 'own.vouchers.fAmount')" :suffix="form.kind === 'percent' ? '%' : 'USD'" inputmode="decimal" />
      <AppField v-model="form.applies_to" as="select" :label="t('own.vouchers.fApplies')" :options="scopeChoices" />
      <div v-if="form.applies_to !== 'event_pass'" class="vo-full" style="display: grid; gap: 6px">
        <span class="rs-eyebrow">{{ t('own.vouchers.fPackages') }}</span>
        <div class="vo-row"><AppCheck v-model="form.packages.roots" label="Root" /><AppCheck v-model="form.packages.square" label="Square" /><AppCheck v-model="form.packages.grove" label="Grove" /></div>
        <small class="oc-mut">{{ t('own.vouchers.fPackagesHint') }}</small>
      </div>
      <AppField v-model="form.valid_from" type="date" :label="t('own.vouchers.fFrom')" optional />
      <AppField v-model="form.valid_until" type="date" :label="t('own.vouchers.fUntil')" optional />
      <AppField v-model="form.max_uses" :label="t('own.vouchers.fMaxUses')" :hint="t('own.vouchers.fMaxUsesHint')" optional inputmode="numeric" />
      <div class="vo-full vo-tight">
        <AppCheck v-model="form.once_per_org" :label="t('own.vouchers.fOncePerOrg')" />
        <AppCheck v-model="form.new_customers_only" :label="t('own.vouchers.fNewOnly')" />
        <AppCheck v-model="form.stackable" :label="t('own.vouchers.fStackable')" data-testid="f-stackable" />
      </div>
      <AppField v-model="form.partner_id" as="select" :label="t('own.vouchers.fPartner')" :options="partnerChoices" />
      <AppField class="vo-full" v-model="form.note" :label="t('own.vouchers.fNote')" optional />
      <AppCheck class="vo-full" v-model="form.active" :label="t('own.vouchers.fActive')" />
    </div>
    <AppAlert v-if="formError" tone="danger" role="alert">{{ formError }}</AppAlert>
  </ConfirmDialog>

  <ConfirmDialog v-if="pForm" :title="t(pForm.id ? 'own.vouchers.editPartner' : 'own.vouchers.newPartner')" :verb="t('own.vouchers.save')" tone="primary" wide :confirm-disabled="busy" @confirm="savePartner" @cancel="pForm = null">
    <div class="vo-form">
      <AppField v-model="pForm.name" :label="t('own.vouchers.fName')" />
      <AppField v-model="pForm.email" :label="t('own.vouchers.fEmail')" :hint="t('own.vouchers.fEmailHint')" optional />
      <AppField v-model="pForm.commission" :label="t('own.vouchers.fCommission')" suffix="%" :hint="t('own.vouchers.fCommissionHint')" inputmode="numeric" />
      <AppCheck class="vo-full" v-model="pForm.active" :label="t('own.vouchers.fActive')" />
    </div>
    <AppAlert v-if="pError" tone="danger" role="alert">{{ pError }}</AppAlert>
  </ConfirmDialog>

  <ConfirmDialog v-if="redemptionsOf" :title="t('own.vouchers.usesOf', { code: redemptionsOf.code })" :verb="t('own.vouchers.close')" tone="primary" wide @confirm="redemptionsOf = null" @cancel="redemptionsOf = null">
    <table class="oc-tbl">
      <thead><tr><th>{{ t('own.vouchers.colWhen') }}</th><th>{{ t('own.vouchers.colSquare') }}</th><th>{{ t('own.vouchers.colBefore') }}</th><th>{{ t('own.vouchers.colOffAmount') }}</th><th>{{ t('own.vouchers.colPaid') }}</th></tr></thead>
      <tbody>
        <tr v-for="r in redemptions" :key="r.order_id">
          <td>{{ day(r.paid_at) }}</td><td>{{ r.square_name }}<small class="oc-mut" style="display: block">{{ r.organization_name }}</small></td><td>{{ usd(r.list_minor) }}</td><td>{{ usd(r.discount_minor) }}</td><td>{{ usd(r.paid_minor) }}</td>
        </tr>
      </tbody>
    </table>
  </ConfirmDialog>

  <ConfirmDialog v-if="report" :title="t('own.vouchers.reportOf', { name: report.partner.name })" :verb="t('own.vouchers.close')" tone="primary" wide @confirm="report = null" @cancel="report = null">
    <p class="oc-mut">{{ t('own.vouchers.reportNote', { percent: report.partner.commission_percent }) }}</p>
    <table class="oc-tbl" data-testid="partner-report">
      <thead><tr><th>{{ t('own.vouchers.colCode') }}</th><th>{{ t('own.vouchers.colUses') }}</th><th>{{ t('own.vouchers.colRevenue') }}</th><th>{{ t('own.vouchers.colGiven') }}</th><th>{{ t('own.vouchers.colOwed') }}</th></tr></thead>
      <tbody>
        <tr v-for="l in report.lines" :key="l.code"><td>{{ l.code }}</td><td>{{ l.uses }}</td><td>{{ usd(l.revenue_minor) }}</td><td>{{ usd(l.discount_minor) }}</td><td>{{ usd(l.commission_minor) }}</td></tr>
        <tr><td><b>{{ t('own.vouchers.total') }}</b></td><td><b>{{ report.uses }}</b></td><td><b>{{ usd(report.revenue_minor) }}</b></td><td><b>{{ usd(report.discount_minor) }}</b></td><td><b>{{ usd(report.commission_minor) }}</b></td></tr>
      </tbody>
    </table>
  </ConfirmDialog>
</template>

<style scoped>
.vo-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px 20px; max-height: 64vh; overflow: auto; padding: 10px 12px 10px 10px; margin: 0 -4px }
.vo-full { grid-column: 1 / -1 }
.vo-form { align-items: start }
.vo-row { display: flex; flex-wrap: wrap; gap: 4px 28px }
.vo-tight { display: grid; gap: 2px }
.vo-row :deep(.rs-check), .vo-tight :deep(.rs-check) { min-height: 32px; padding-block: 4px }

/* the rule strip */
.vo-rule { display: flex; gap: 28px; margin: 18px 0; padding: 14px 0; border-top: 2px solid var(--color-brass); border-bottom: 1px solid var(--color-border); flex-wrap: wrap }
.vo-rule div { flex: 1; min-width: 200px; font-size: 12.5px; color: var(--color-text-muted) }
.vo-rule b { display: block; font: 500 9.5px var(--font-sans); letter-spacing: 0.12em; text-transform: uppercase; color: var(--color-brass-text); margin-bottom: 4px }
.vo-rule span { color: var(--color-text) }

/* two columns: the lists, and the rules beside them */
.vo-grid { display: grid; grid-template-columns: minmax(0, 1fr) 330px; gap: 20px; align-items: start }
.vo-grid > * { min-width: 0 }
.vo-main, .vo-side { display: flex; flex-direction: column; gap: 18px }
.vo-side { position: sticky; top: 72px }
.vo-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--shape-surface)}
.vo-ch { display: flex; align-items: center; gap: 12px; padding: 14px 18px; border-bottom: 1px solid var(--color-border) }
.vo-ch h3 { margin: 0; font: 500 9.5px var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-text-muted) }
.vo-n { font: 500 20px var(--font-display) }
.vo-sp { flex: 1 }
.vo-empty { padding: 26px 18px; color: var(--color-text-muted) }
.vo-empty b { display: block; color: var(--color-text); font: 500 18px var(--font-display); margin-bottom: 2px }
.vo-pad { padding: 16px 18px; display: flex; flex-direction: column; gap: 14px }

/* a voucher and a partner row */
.vo-vr { display: flex; flex-wrap: wrap; gap: 14px 26px; align-items: center; padding: 16px 18px; border-top: 1px solid var(--color-border) }
.vo-ch + .vo-vr, .vo-ch + .vo-empty { border-top: 0 }
.vo-vr.off { opacity: 0.6 }
.vo-vr > div { min-width: 0 }
.vo-id { display: flex; align-items: center; gap: 14px; flex: 1 1 230px }
.vo-off { font: 500 24px/1 var(--font-display) }
.vo-code { font: 600 13px ui-monospace, Menlo, monospace; letter-spacing: 0.04em; color: var(--color-text); background: var(--color-bg); border: 1px dashed var(--color-brass); border-radius: var(--shape-control); padding: 4px 9px; display: inline-block; cursor: pointer }
.vo-code:hover { background: color-mix(in srgb, var(--color-brass) 18%, var(--color-bg)) }
.vo-tags { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 6px }
.vo-tg { font-size: 11px; border: 1px solid var(--color-border); border-radius: var(--shape-control); padding: 1px 9px; background: var(--color-bg) }
.vo-meta { display: flex; gap: 26px; flex-wrap: wrap; flex: 2 1 280px; font-size: var(--text-sm) }
.vo-meta small { display: block; font: 500 9.5px var(--font-sans); letter-spacing: 0.12em; text-transform: uppercase; color: var(--color-text-muted); margin-bottom: 3px }
.vo-meter { height: 4px; border-radius: 9px; background: var(--color-border); margin-top: 5px; width: 90px; overflow: hidden }
.vo-meter i { display: block; height: 100%; background: var(--color-brass) }
.vo-acts { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; flex: 1 1 100%; padding-top: 12px; border-top: 1px dashed var(--color-border) }
.vo-sw { display: inline-flex; align-items: center; gap: 8px; border: 0; background: none; cursor: pointer; padding: 0; margin-right: auto; font: inherit; font-size: 12px; color: var(--color-text) }
.vo-tgl { width: 32px; height: 18px; border-radius: var(--shape-control); background: var(--color-border); position: relative; transition: 0.15s }
.vo-tgl:after { content: ""; position: absolute; left: 2px; top: 2px; width: 14px; height: 14px; border-radius: 50%; background: var(--color-surface); transition: 0.15s }
.vo-sw.on .vo-tgl { background: var(--color-brass) }
.vo-sw.on .vo-tgl:after { left: 16px }
.vo-pr .vo-acts { flex: 0 0 auto; border-top: 0; padding-top: 0; margin-left: auto }

/* how codes combine */
.vo-opt { display: flex; gap: 10px; align-items: flex-start; border: 1px solid var(--color-border); border-radius: var(--shape-inner); padding: 10px 12px; cursor: pointer; background: var(--color-bg); text-align: left; width: 100%; font: inherit; color: var(--color-text) }
.vo-opt:hover { border-color: var(--color-brass) }
.vo-opt.on { border-color: var(--color-brass); background: var(--color-brass-subtle); box-shadow: 0 0 0 1px var(--color-brass) }
.vo-opt i { flex: none; width: 14px; height: 14px; border-radius: 50%; border: 1.5px solid var(--color-text-muted); margin-top: 2px }
.vo-opt.on i { border: 4px solid var(--color-brass) }
.vo-opt b { display: block; font-size: 12.5px }
.vo-opt small { color: var(--color-text-muted); font-size: 11.5px }
.vo-step { display: flex; align-items: center; justify-content: space-between; gap: 10px; font-size: 12.5px }
.vo-stp { display: inline-flex; border: 1px solid var(--color-border); border-radius: var(--shape-control); overflow: hidden; background: var(--color-surface) }
.vo-stp button { border: 0; background: none; width: 30px; height: 30px; cursor: pointer; font-size: 15px; color: var(--color-text) }
.vo-stp button:hover { background: var(--color-bg) }
.vo-stp span { min-width: 34px; text-align: center; line-height: 30px; font-weight: 600; border-inline: 1px solid var(--color-border) }
.vo-save { display: flex; gap: 10px; align-items: center; font-size: var(--text-sm) }

/* the play checkout */
.vo-sim { background: var(--color-brass-subtle); color: var(--color-text); border: 1px solid var(--color-border); border-top: 1px solid var(--color-border); border-radius: var(--shape-surface); padding: 18px; display: flex; flex-direction: column; gap: 12px }
.vo-sim h3 { margin: 0; font: 500 9.5px var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-brass-text) }
.vo-ln { display: flex; justify-content: space-between; align-items: baseline; font-variant-numeric: tabular-nums; gap: 10px }
.vo-ln.d { opacity: 0.9 }
.vo-ln.ig { opacity: 0.55 }
.vo-ln.ig .vo-x { text-decoration: line-through }
.vo-x { display: inline-flex; gap: 6px; align-items: center }
.vo-price { display: inline-flex; align-items: center; gap: 8px } /* the $ and the box have a gap (W25-R45) */
.vo-rm { border: 0; background: none; color: inherit; opacity: 0.6; cursor: pointer; padding: 0 2px; font: inherit }
.vo-rm:hover { opacity: 1 }
.vo-tot { border-top: 1px solid var(--color-brass); padding-top: 10px; display: flex; justify-content: space-between; align-items: baseline }
.vo-tot b { font: 500 34px/1 var(--font-display) }
.vo-sim input { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--shape-field); padding: 5px 9px; color: inherit; width: 80px; text-align: right; font: inherit }
.vo-add { display: flex; gap: 8px; flex-wrap: wrap }
.vo-addbtn { background: var(--color-surface); color: var(--color-text); border: 1px solid var(--color-border-strong); border-radius: var(--shape-control); min-height: 30px; padding: 0 14px; font: inherit; font-weight: 500; font-size: var(--text-xs); cursor: pointer }
.vo-addbtn:hover { background: var(--color-brass-subtle); border-color: var(--color-brass-text) }
.vo-sim small { opacity: 0.65; font-size: 11.5px }

@media (max-width: 1280px) { .vo-grid { grid-template-columns: minmax(0, 1fr) } .vo-side { position: static } }
</style>
