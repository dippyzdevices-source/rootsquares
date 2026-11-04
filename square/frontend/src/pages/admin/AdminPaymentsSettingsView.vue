<script setup lang="ts">
import { moduleEnabled } from '../../services/modules'
import { squareProfile } from '../../services/squareConfig'
import SettingsSectionNav from '../../components/SettingsSectionNav.vue'
import SettingsBackButton from '../../components/SettingsBackButton.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseFileButton from '../../components/ui/BaseFileButton.vue'
import VippsConnectCard from '../../components/VippsConnectCard.vue'
import StripeConnectCard from '../../components/StripeConnectCard.vue'
import { deleteVippsQrImage, fetchAdminSettings, updateAdminSettings, uploadVippsQrImage, ValidationError } from '../../services/adminSettingsApi'
import { fetchVippsStatus } from '../../services/adminPaymentsApi'
import { useToast } from '../../composables/useToast'
import { formatPrice } from '../../utils/money'

const toast = useToast()

const loading = ref(true)
const saving = ref(false)
const error = ref(false)
const configured = ref(false)
const stripeConnected = ref(false)
const qrImageUrl = ref<string | null>(null) // the uploaded picture of the Vipps QR code; saved by the upload itself, not by Save
const qrBusy = ref(false)
const feeErrors = ref<Record<string, string>>({})
const ticketsOn = moduleEnabled('tickets') // W8-R29
const membershipsOn = moduleEnabled('memberships')
const currency = squareProfile.currency

// The three ways to pay. `key` is the stored method name (settings field prefix); `auto` = the provider
// confirms the payment itself, otherwise an admin confirms the money arrived. Fixed part is entered in kr
// here and stored in øre.
const METHODS = [
  {
    key: 'vipps_qr' as const,
    name: 'Vipps-QR',
    auto: false,
    description: 'Customers pay to your own Vipps number, then say they have paid. Needs the number below.',
    hint: 'An admin confirms the money arrived.',
  },
  {
    key: 'vipps_app' as const,
    name: 'Vipps-App',
    auto: true,
    description: `${ticketsOn && membershipsOn ? 'Tickets and memberships' : ticketsOn ? 'Tickets' : membershipsOn ? 'Memberships' : 'Payments'} paid in the Vipps app, plus the convenience fee.`,
    hint: 'Vipps confirms the payment itself.',
  },
  {
    key: 'cash' as const,
    name: 'Cash',
    auto: false,
    description: `Paid in person. Each event chooses whether to offer it;${membershipsOn ? ' memberships can be paid in cash too.' : ''}`,
    hint: 'An admin confirms the money arrived. Events can override the ticket wording.',
  },
  {
    key: 'stripe' as const,
    name: 'Card (Stripe)',
    auto: true,
    description: 'Customers pay by card on a Stripe page. Stripe confirms the payment itself. Needs your own Stripe account, connected above.',
    hint: 'Stripe confirms the payment itself.',
  },
]
type Key = (typeof METHODS)[number]['key']

interface MethodForm {
  on: boolean
  convenience: string
  processing: string
  fixed: string
}
interface BankForm {
  bank_account_holder: string
  bank_name: string
  bank_account_number: string
  bank_iban: string
  bank_bic: string
  bank_transfer_note: string
}
interface Form {
  methods: Record<Key, MethodForm>
  cashTicketNote: string
  cashMembershipNote: string
  vippsNumber: string
  bankOn: boolean
  bank: BankForm
}
const blankBank = (): BankForm => ({ bank_account_holder: '', bank_name: '', bank_account_number: '', bank_iban: '', bank_bic: '', bank_transfer_note: '' })

const blank = (): Form => ({
  methods: {
    vipps_qr: { on: true, convenience: '0', processing: '0', fixed: '0' },
    vipps_app: { on: false, convenience: '5', processing: '2.99', fixed: '1' },
    cash: { on: false, convenience: '0', processing: '0', fixed: '0' },
    stripe: { on: false, convenience: '0', processing: '0', fixed: '0' },
  },
  cashTicketNote: '',
  cashMembershipNote: '',
  vippsNumber: '',
  bankOn: false,
  bank: blankBank(),
})

const form = reactive<Form>(blank())
// A number input hands back a number while the loaded value is a string, so compare as text.
const snapshot = () => JSON.stringify(form, (_key, value) => (typeof value === 'number' ? String(value) : value))
const saved = ref(JSON.stringify(blank())) // what the server has, to tell unsaved changes from none

const dirty = computed(() => snapshot() !== saved.value)
// Vipps QR only counts while it has a number to pay to; bank transfer only while it has a holder and an account number or IBAN.
const qrHasDetails = computed(() => form.vippsNumber.trim() !== '' || !!qrImageUrl.value)
const qrUsable = computed(() => form.methods.vipps_qr.on && qrHasDetails.value)
const bankUsable = computed(() => form.bankOn && form.bank.bank_account_holder.trim() !== '' && (form.bank.bank_account_number.trim() !== '' || form.bank.bank_iban.trim() !== ''))
const noMethodOn = computed(() => !qrUsable.value && !form.methods.vipps_app.on && !form.methods.cash.on && !(form.methods.stripe.on && stripeConnected.value) && !bankUsable.value)

const EXAMPLES = [
  'Your place is not confirmed until you pay. Food is not guaranteed.',
  'Pay your membership in cash to a board member.',
]

// --- Fee preview: what a payment of `price` kr really costs (customer fee on top, provider's cut off) ---
const price = ref('500')
const num = (v: string) => Number(v) || 0
const toOre = (kr: number) => Math.round(kr * 100)

// One tab per way to pay (more later, for example Stripe). Everything stays in one form with one Save bar; a tab only decides what is shown.
type TabKey = 'vipps' | 'card' | 'cash' | 'bank'
const TABS: { key: TabKey; label: string }[] = [
  { key: 'vipps', label: 'Vipps' },
  { key: 'card', label: 'Card' },
  { key: 'cash', label: 'Cash' },
  { key: 'bank', label: 'Bank transfer' },
]
const tab = ref<TabKey>('vipps')
const tabOfMethod = (key: Key): TabKey => (key === 'cash' ? 'cash' : key === 'stripe' ? 'card' : 'vipps')
const tabIsOn = (key: TabKey) =>
  key === 'bank' ? form.bankOn : METHODS.some((m) => tabOfMethod(m.key) === key && form.methods[m.key].on)

const preview = computed(() => {
  const p = Math.max(num(price.value), 0)
  return METHODS.filter((m) => form.methods[m.key].on).map((m) => {
    const f = form.methods[m.key]
    const convenience = (p * num(f.convenience)) / 100
    const customerPays = p + convenience
    const providerTakes = (customerPays * num(f.processing)) / 100 + num(f.fixed)
    return { key: m.key, name: m.name, convenience, customerPays, providerTakes, youReceive: customerPays - providerTakes }
  })
})
const tabPreview = computed(() => preview.value.filter((row) => tabOfMethod(row.key as Key) === tab.value))
const avgCost = computed(() =>
  preview.value.length ? preview.value.reduce((s, r) => s + r.providerTakes, 0) / preview.value.length : null,
)
const avgExtra = computed(() =>
  preview.value.length ? preview.value.reduce((s, r) => s + r.convenience, 0) / preview.value.length : null,
)
const kr = (value: number) => formatPrice(toOre(value))

function applySettings(settings: Record<string, unknown>) {
  const next = blank()
  next.methods.vipps_qr.on = (settings.vipps_qr_enabled as boolean | undefined) ?? false
  next.methods.vipps_app.on = (settings.vipps_app_public as boolean | undefined) ?? false
  next.methods.cash.on = (settings.cash_enabled as boolean | undefined) ?? false
  next.methods.stripe.on = (settings.stripe_enabled as boolean | undefined) ?? false
  for (const { key } of METHODS) {
    const conv = settings[`${key}_convenience_percent`]
    const proc = settings[`${key}_processing_percent`]
    const fixed = settings[`${key}_processing_fixed_ore`]
    if (typeof conv === 'number') next.methods[key].convenience = String(conv)
    if (typeof proc === 'number') next.methods[key].processing = String(proc)
    if (typeof fixed === 'number') next.methods[key].fixed = String(fixed / 100)
  }
  next.cashTicketNote = (settings.cash_ticket_note as string | undefined) ?? ''
  next.cashMembershipNote = (settings.cash_membership_note as string | undefined) ?? ''
  next.vippsNumber = (settings.vipps_number as string | undefined) ?? ''
  qrImageUrl.value = (settings.vipps_qr_image_url as string | null | undefined) ?? null
  next.bankOn = (settings.bank_transfer_enabled as boolean | undefined) ?? false
  for (const field of Object.keys(next.bank) as (keyof BankForm)[]) next.bank[field] = (settings[field] as string | undefined) ?? ''
  Object.assign(form.methods.vipps_qr, next.methods.vipps_qr)
  Object.assign(form.methods.vipps_app, next.methods.vipps_app)
  Object.assign(form.methods.cash, next.methods.cash)
  Object.assign(form.methods.stripe, next.methods.stripe)
  form.cashTicketNote = next.cashTicketNote
  form.cashMembershipNote = next.cashMembershipNote
  form.vippsNumber = next.vippsNumber
  form.bankOn = next.bankOn
  Object.assign(form.bank, next.bank)
  saved.value = snapshot()
}

function discard() {
  const original = JSON.parse(saved.value) as Form
  Object.assign(form.methods.vipps_qr, original.methods.vipps_qr)
  Object.assign(form.methods.vipps_app, original.methods.vipps_app)
  Object.assign(form.methods.cash, original.methods.cash)
  Object.assign(form.methods.stripe, original.methods.stripe)
  form.cashTicketNote = original.cashTicketNote
  form.cashMembershipNote = original.cashMembershipNote
  form.vippsNumber = original.vippsNumber
  form.bankOn = original.bankOn
  Object.assign(form.bank, original.bank)
  feeErrors.value = {}
}

function payload() {
  const out: Record<string, unknown> = {
    vipps_qr_enabled: form.methods.vipps_qr.on,
    vipps_app_public: form.methods.vipps_app.on,
    cash_enabled: form.methods.cash.on,
    stripe_enabled: form.methods.stripe.on,
    cash_ticket_note: form.cashTicketNote,
    cash_membership_note: form.cashMembershipNote,
    vipps_number: form.vippsNumber.trim(),
    bank_transfer_enabled: form.bankOn,
    ...form.bank,
  }
  for (const { key } of METHODS) {
    out[`${key}_convenience_percent`] = num(form.methods[key].convenience)
    out[`${key}_processing_percent`] = num(form.methods[key].processing)
    out[`${key}_processing_fixed_ore`] = toOre(num(form.methods[key].fixed))
  }
  return out
}

async function load() {
  loading.value = true
  error.value = false
  try {
    const [settings, status] = await Promise.all([fetchAdminSettings(), fetchVippsStatus()])
    applySettings(settings as unknown as Record<string, unknown>)
    configured.value = status.configured
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

/** After a method is disconnected the server has switched it off: show that without losing other unsaved edits. */
async function refreshSwitches() {
  try {
    const s = (await fetchAdminSettings()) as unknown as Record<string, unknown>
    const on = { vipps_app: !!s.vipps_app_public, stripe: !!s.stripe_enabled, vipps_qr: !!s.vipps_qr_enabled } as const
    const original = JSON.parse(saved.value) as Form
    for (const key of ['vipps_app', 'stripe', 'vipps_qr'] as const) {
      form.methods[key].on = on[key]
      original.methods[key].on = on[key]
    }
    saved.value = JSON.stringify(original)
  } catch {
    /* the next load shows the truth */
  }
}

async function pickQrImage(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  qrBusy.value = true
  feeErrors.value = {}
  try {
    const settings = await uploadVippsQrImage(file)
    qrImageUrl.value = (settings as unknown as Record<string, string | null>).vipps_qr_image_url ?? null
    toast.success('Vipps QR picture saved')
  } catch (e) {
    toast.error(e instanceof ValidationError ? (e.errors.file ?? 'Could not upload the picture') : 'Could not upload the picture')
  } finally {
    qrBusy.value = false
  }
}

async function removeQrImage() {
  qrBusy.value = true
  try {
    const settings = (await deleteVippsQrImage()) as unknown as Record<string, unknown>
    qrImageUrl.value = null
    if (!settings.vipps_qr_enabled) await refreshSwitches() // with nothing left to pay to, the server switched Vipps QR off
    toast.success('Vipps QR picture removed')
  } catch {
    toast.error('Could not remove the picture')
  } finally {
    qrBusy.value = false
  }
}

async function save() {
  saving.value = true
  feeErrors.value = {}
  try {
    const settings = await updateAdminSettings(payload())
    applySettings(settings as unknown as Record<string, unknown>)
    toast.success('Payment methods saved')
  } catch (e) {
    if (e instanceof ValidationError) feeErrors.value = e.errors
    toast.error('Could not save the payment settings')
  } finally {
    saving.value = false
  }
}

const errorFor = (key: Key) =>
  feeErrors.value[`${key}_convenience_percent`] ||
  feeErrors.value[`${key}_processing_percent`] ||
  feeErrors.value[`${key}_processing_fixed_ore`] ||
  ''

onMounted(load)
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Settings</h1>
        <p class="ds-intro">Site-wide settings and content that do not change often.</p>
      </div>
    </div>

    <SettingsSectionNav />

    <div class="pay-settings">
      <div>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
          <h2 class="ds-display ds-display-s">Payments</h2>
          <SettingsBackButton />
        </div>
        <p class="ds-meta" style="max-width: 62ch; margin-top: var(--ds-space-1)">
          Choose how customers can pay, and what each method costs. Changes apply to new payments only.
        </p>
      </div>

      <BaseLoadingState v-if="loading" label="Loading payment settings…" />
      <div v-else-if="error" class="ds-alert ds-alert-danger"><div>Couldn't load the payment settings. Please try again shortly.</div></div>
      <template v-else>
        <div class="pay-stats">
          <div class="ds-card ds-card-sunken pay-stat">
            <small>Methods on</small>
            <strong class="methods-on">{{ preview.length }} of {{ METHODS.length }}</strong>
          </div>
          <div class="ds-card ds-card-sunken pay-stat">
            <small>Avg. cost to you</small>
            <strong class="avg-cost">{{ avgCost === null ? '—' : kr(avgCost) }}</strong>
          </div>
          <div class="ds-card ds-card-sunken pay-stat">
            <small>Customer pays extra</small>
            <strong class="avg-extra">{{ avgExtra === null ? '—' : kr(avgExtra) }}</strong>
          </div>
        </div>

        <div v-if="noMethodOn" class="ds-alert ds-alert-warning no-method-on">
          <div>At least one payment method has to stay on, otherwise customers cannot pay.</div>
        </div>

        <nav class="ds-tabs pay-tabs" role="tablist" aria-label="Payment methods">
          <button
            v-for="t in TABS"
            :key="t.key"
            type="button"
            role="tab"
            class="ds-tab"
            :class="{ 'ds-tab-active': tab === t.key }"
            :aria-selected="tab === t.key"
            :data-tab="t.key"
            @click="tab = t.key"
          >
            {{ t.label }}<span v-if="tabIsOn(t.key)" class="pay-tab-on" title="On" aria-label="on"></span>
          </button>
        </nav>

        <StripeConnectCard v-show="tab === 'card'" @changed="(connected: boolean) => { const was = stripeConnected; stripeConnected = connected; if (was && !connected) void refreshSwitches() }" />
        <div v-if="!stripeConnected" v-show="tab === 'card'" class="ds-alert ds-alert-info stripe-not-connected">
          <div>Connect your Stripe account above to switch on card payments. Without it, customers cannot pay by card.</div>
        </div>
        <VippsConnectCard v-show="tab === 'vipps'" @changed="(connected: boolean) => { const was = configured; configured = connected; if (was && !connected) void refreshSwitches() }" />
        <div v-if="!configured" v-show="tab === 'vipps'" class="ds-alert ds-alert-info vipps-not-configured">
          <div>Connect your Vipps account above to switch on Vipps-App. Without it, customers cannot pay in the Vipps app.</div>
        </div>
        <div v-if="!form.methods.vipps_app.on" v-show="tab === 'vipps'" class="ds-alert ds-alert-warning pay-test">
          <div>
            <strong>Test before going live.</strong> Run the 1 {{ currency }} test payment from
            <router-link to="/admin/payments" style="font-weight: 600">Payments</router-link>. The button disappears once Vipps-App is on.
          </div>
        </div>

        <div class="pay-layout">
          <div class="pay-methods">
            <section
              v-for="m in METHODS"
              :key="m.key"
              v-show="tabOfMethod(m.key) === tab"
              class="ds-card pay-method"
              :class="{ 'pay-method-off': !form.methods[m.key].on }"
              :data-method="m.key"
            >
              <div class="pay-head">
                <div class="pay-name">
                  <strong>{{ m.name }}</strong>
                  <span class="ds-meta">{{ m.description }}</span>
                </div>
                <span class="ds-badge" :class="m.auto ? 'ds-badge-success' : 'ds-badge-warning'">{{ m.auto ? 'Auto-approved' : 'Admin approves' }}</span>
                <label class="ds-switch pay-switch" :style="{ opacity: (m.key === 'vipps_app' && !configured) || (m.key === 'stripe' && !stripeConnected) || (m.key === 'vipps_qr' && !qrHasDetails) ? 0.5 : 1 }">
                  <input
                    v-model="form.methods[m.key].on"
                    type="checkbox"
                    :aria-label="`Enable ${m.name} payment`"
                    :disabled="(m.key === 'vipps_app' && !configured) || (m.key === 'stripe' && !stripeConnected) || (m.key === 'vipps_qr' && !qrHasDetails)"
                  />
                  <span class="ds-switch-track"><span class="ds-switch-thumb"></span></span>
                </label>
              </div>

              <div v-if="m.key === 'vipps_qr'" class="pay-body pay-qr-details">
                <div class="pay-wording">
                  <label class="ds-field vipps-number">
                    <span class="ds-field-label">Your Vipps number</span>
                    <input v-model="form.vippsNumber" class="ds-input" inputmode="numeric" maxlength="12" aria-label="Your Vipps number" placeholder="e.g. 123456" />
                    <span v-if="feeErrors.vipps_number" class="ds-field-error">{{ feeErrors.vipps_number }}</span>
                    <span v-else class="ds-field-hint">Digits only.</span>
                  </label>
                  <div class="ds-field vipps-qr-upload">
                    <span class="ds-field-label">Your Vipps QR picture</span>
                    <div v-if="qrImageUrl" style="display: flex; align-items: center; gap: var(--ds-space-3); flex-wrap: wrap">
                      <img :src="qrImageUrl" alt="Your Vipps QR code" style="width: 120px; height: 120px; object-fit: contain; border: 1px solid var(--ds-border, #ddd); border-radius: var(--ds-radius-md, 8px)" />
                      <BaseButton type="button" size="sm" variant="secondary" class="qr-remove" :disabled="qrBusy" @click="removeQrImage">Remove picture</BaseButton>
                    </div>
                    <div><BaseFileButton accept="image/*" size="sm" class="qr-file" :disabled="qrBusy" @change="pickQrImage">{{ qrImageUrl ? 'Replace picture' : 'Upload picture' }}</BaseFileButton></div>
                    <span class="ds-field-hint">Upload the QR picture from your Vipps app. Add the number, the picture or both: customers see what you add. Vipps-QR can be switched on only when one of them is there.</span>
                  </div>
                </div>
                <p v-if="feeErrors.vipps_qr_enabled" class="ds-field-error-text">{{ feeErrors.vipps_qr_enabled }}</p>
              </div>

              <div v-if="form.methods[m.key].on" class="pay-body">
                <div class="pay-fees">
                  <label class="ds-field">
                    <span class="ds-field-label">Convenience fee</span>
                    <span class="ds-meta pay-fee-hint">Charged to the customer, on top of the price</span>
                    <span class="ds-field-control">
                      <input v-model="form.methods[m.key].convenience" type="number" step="0.01" min="0" max="100" class="ds-field-input" :aria-label="`${m.name} convenience fee percent`" />
                      <span class="ds-meta">%</span>
                    </span>
                  </label>
                  <label class="ds-field">
                    <span class="ds-field-label">Processing fee</span>
                    <span class="ds-meta pay-fee-hint">Taken by the provider (% of payment)</span>
                    <span class="ds-field-control">
                      <input v-model="form.methods[m.key].processing" type="number" step="0.01" min="0" max="100" class="ds-field-input" :aria-label="`${m.name} processing fee percent`" />
                      <span class="ds-meta">%</span>
                    </span>
                  </label>
                  <label class="ds-field">
                    <span class="ds-field-label">Fixed part</span>
                    <span class="ds-meta pay-fee-hint">Provider's fee per payment</span>
                    <span class="ds-field-control">
                      <input v-model="form.methods[m.key].fixed" type="number" step="0.01" min="0" class="ds-field-input" :aria-label="`${m.name} fixed fee`" />
                      <span class="ds-meta">{{ currency }}</span>
                    </span>
                  </label>
                </div>
                <p v-if="errorFor(m.key)" class="ds-field-error-text">{{ errorFor(m.key) }}</p>

                <div v-if="m.key === 'cash'" class="pay-wording">
                  <label v-if="ticketsOn" class="ds-field">
                    <span class="ds-field-label">Wording for tickets</span>
                    <span class="ds-meta pay-fee-hint">Shown at checkout and in the order email</span>
                    <span class="ds-textarea-control">
                      <textarea v-model="form.cashTicketNote" rows="3" maxlength="1000" class="ds-textarea" :placeholder="EXAMPLES[0]" aria-label="Cash wording for tickets"></textarea>
                    </span>
                    <button type="button" class="ds-tag use-example" data-ex="0" @click="form.cashTicketNote = EXAMPLES[0]">Use example</button>
                  </label>
                  <label v-if="membershipsOn" class="ds-field">
                    <span class="ds-field-label">Wording for memberships</span>
                    <span class="ds-meta pay-fee-hint">Shown to members paying in cash</span>
                    <span class="ds-textarea-control">
                      <textarea v-model="form.cashMembershipNote" rows="3" maxlength="1000" class="ds-textarea" :placeholder="EXAMPLES[1]" aria-label="Cash wording for memberships"></textarea>
                    </span>
                    <button type="button" class="ds-tag use-example" data-ex="1" @click="form.cashMembershipNote = EXAMPLES[1]">Use example</button>
                  </label>
                </div>
                <p class="ds-meta pay-method-hint">{{ m.hint }}</p>
              </div>
            </section>

            <section v-show="tab === 'bank'" class="ds-card pay-method" :class="{ 'pay-method-off': !form.bankOn }" data-method="bank_transfer">
              <div class="pay-head">
                <div class="pay-name">
                  <strong>Bank transfer</strong>
                  <span class="ds-meta">Customers transfer the money to your account and write a reference. Works for donations, tickets (each event chooses) and memberships; not for the sign-up drive, which takes payment in person.</span>
                </div>
                <span class="ds-badge ds-badge-warning">Admin approves</span>
                <label class="ds-switch pay-switch">
                  <input v-model="form.bankOn" type="checkbox" aria-label="Enable Bank transfer payment" />
                  <span class="ds-switch-track"><span class="ds-switch-thumb"></span></span>
                </label>
              </div>
              <div v-if="form.bankOn" class="pay-body">
                <div class="pay-wording bank-details-form">
                  <label class="ds-field">
                    <span class="ds-field-label">Account holder</span>
                    <span class="ds-field-control"><input v-model="form.bank.bank_account_holder" type="text" maxlength="200" class="ds-field-input" aria-label="Account holder" /></span>
                    <span v-if="feeErrors.bank_account_holder" class="ds-field-error-text">{{ feeErrors.bank_account_holder }}</span>
                  </label>
                  <label class="ds-field">
                    <span class="ds-field-label">Bank name (optional)</span>
                    <span class="ds-field-control"><input v-model="form.bank.bank_name" type="text" maxlength="200" class="ds-field-input" aria-label="Bank name" /></span>
                  </label>
                  <label class="ds-field">
                    <span class="ds-field-label">Account number</span>
                    <span class="ds-field-control"><input v-model="form.bank.bank_account_number" type="text" maxlength="60" class="ds-field-input" aria-label="Account number" /></span>
                  </label>
                  <label class="ds-field">
                    <span class="ds-field-label">IBAN (optional)</span>
                    <span class="ds-field-control"><input v-model="form.bank.bank_iban" type="text" maxlength="60" class="ds-field-input" aria-label="IBAN" /></span>
                  </label>
                  <label class="ds-field">
                    <span class="ds-field-label">BIC / SWIFT (optional)</span>
                    <span class="ds-field-control"><input v-model="form.bank.bank_bic" type="text" maxlength="30" class="ds-field-input" aria-label="BIC" /></span>
                  </label>
                  <label class="ds-field">
                    <span class="ds-field-label">Note for the payer (optional)</span>
                    <span class="ds-textarea-control"><textarea v-model="form.bank.bank_transfer_note" rows="3" maxlength="1000" class="ds-textarea" aria-label="Bank transfer note"></textarea></span>
                    <span class="ds-field-hint">Shown with the account details, for example how long a transfer may take.</span>
                  </label>
                  <span v-if="!bankUsable" class="ds-field-hint">Needs an account holder and an account number or IBAN before it is offered.</span>
                </div>
              </div>
            </section>

          </div>

          <aside v-show="tab !== 'bank'" class="ds-card pay-preview">
            <h3 class="ds-title" style="margin: 0">Fee preview</h3>
            <p class="ds-meta" style="margin: 0 0 var(--ds-space-3)">See what a payment really costs.</p>
            <label class="ds-field">
              <span class="ds-field-label">Ticket price</span>
              <span class="ds-field-control">
                <input v-model="price" type="number" min="0" class="ds-field-input" aria-label="Ticket price for the preview" />
                <span class="ds-meta">{{ currency }}</span>
              </span>
            </label>
            <p v-if="tabPreview.length === 0" class="ds-meta">No methods enabled.</p>
            <div v-for="row in tabPreview" :key="row.key" class="pay-preview-method" :data-preview="row.key">
              <p class="ds-eyebrow" style="margin: var(--ds-space-3) 0 var(--ds-space-1)">{{ row.name }}</p>
              <p class="pay-row"><span>Customer pays</span><span>{{ kr(row.customerPays) }}</span></p>
              <p class="pay-row"><span>Provider takes</span><span>{{ row.providerTakes > 0.004 ? '−' : '' }}{{ kr(row.providerTakes) }}</span></p>
              <p class="pay-row pay-row-total"><span>You receive</span><span>{{ kr(row.youReceive) }}</span></p>
            </div>
            <p class="ds-meta pay-note">
              Convenience fees are booked in <strong>Collection</strong>; processing fees in <strong>Expenses</strong>. Processing fees are
              estimates, saved when a payment is paid.
            </p>
          </aside>
        </div>

        <div v-if="dirty" class="pay-savebar" role="region" aria-label="Unsaved changes">
          <span class="ds-meta">You have unsaved changes</span>
          <BaseButton type="button" variant="ghost" class="discard-changes" :disabled="saving" @click="discard">Discard</BaseButton>
          <BaseButton type="button" class="save-changes" :disabled="saving || noMethodOn" @click="save">{{ saving ? 'Saving…' : 'Save changes' }}</BaseButton>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
/* A container so the layout follows the width the admin shell leaves, not the screen width. */
.pay-settings { width: 100%; max-width: 1000px; display: flex; flex-direction: column; gap: var(--ds-space-5); container-type: inline-size; }
.pay-tab-on { display: inline-block; width: 7px; height: 7px; margin-left: 8px; border-radius: 50%; background: var(--ds-status-success, #3a7d44); vertical-align: middle; }
.pay-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--ds-space-3); }
.pay-stat { display: flex; flex-direction: column; gap: 2px; padding: var(--ds-space-3) var(--ds-space-4); }
.pay-stat small { font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ds-text-muted); }
.pay-stat strong { font-family: var(--ds-font-display); font-size: var(--ds-text-title); font-weight: 400; color: var(--ds-text-heading); }
.pay-layout { display: grid; grid-template-columns: minmax(0, 1fr) 290px; gap: var(--ds-space-5); align-items: start; }
.pay-methods { display: flex; flex-direction: column; gap: var(--ds-space-3); min-width: 0; }
.pay-method { padding: 0; overflow: hidden; }
.pay-head { display: flex; gap: var(--ds-space-3); align-items: center; padding: var(--ds-space-4) var(--ds-space-5); }
.pay-name { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.pay-name strong { font-size: var(--ds-text-body-l); color: var(--ds-text-heading); }
.pay-method-off .pay-name { opacity: 0.55; }
.pay-switch { flex: none; }
.pay-body { border-top: 1px solid var(--ds-border-hairline); padding: var(--ds-space-4) var(--ds-space-5) var(--ds-space-5); display: flex; flex-direction: column; gap: var(--ds-space-3); }
.pay-fees { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--ds-space-3); }
/* Two lines tall on purpose, so the three inputs line up even when one hint is shorter. */
.pay-fee-hint { display: block; font-size: 12px; line-height: 1.4; min-height: 2.8em; margin-bottom: var(--ds-space-2); }
/* Inputs sit on the bottom edge of their column, so they line up however many lines each hint needs. */
.pay-fees .ds-field, .pay-wording .ds-field { display: flex; flex-direction: column; gap: 0; }
.pay-fees .ds-field-control { margin-top: auto; }
.pay-wording { display: grid; grid-template-columns: 1fr 1fr; gap: var(--ds-space-3); padding-top: var(--ds-space-3); border-top: 1px dashed var(--ds-border-hairline); }
.pay-method-hint { margin: 0; }
.use-example { align-self: flex-start; margin-top: var(--ds-space-3); }
.pay-preview { position: sticky; top: var(--ds-space-4); display: flex; flex-direction: column; gap: var(--ds-space-1); }
.pay-row { display: flex; justify-content: space-between; gap: var(--ds-space-3); margin: 0; padding: 4px 0; font-size: 13px; }
.pay-row span:first-child { color: var(--ds-text-muted); }
.pay-row-total { border-top: 1px solid var(--ds-border-hairline); margin-top: 4px; padding-top: 8px; font-weight: 600; }
.pay-row-total span:first-child { color: var(--ds-text-heading); }
.pay-note { margin: var(--ds-space-3) 0 0; padding: var(--ds-space-3); background: var(--ds-surface-sunken); border-radius: var(--ds-radius-md); font-size: 12px; }
/* Stays at the bottom of the viewport while there is something to save. */
.pay-savebar > span { flex: 1; }
.pay-savebar { position: sticky; bottom: 0; z-index: 5; display: flex; align-items: center; gap: var(--ds-space-3); flex-wrap: wrap; padding: var(--ds-space-3) var(--ds-space-4); background: var(--ds-surface-card); border: 1px solid var(--ds-border-default); border-radius: var(--ds-radius-lg); box-shadow: var(--ds-shadow-md); }
@container (max-width: 800px) {
  .pay-layout { grid-template-columns: minmax(0, 1fr); }
  .pay-preview { position: static; }
  /* One compact row per figure instead of three tall boxes. */
  .pay-stats { grid-template-columns: minmax(0, 1fr); gap: var(--ds-space-2); }
  .pay-stat { flex-direction: row; align-items: baseline; justify-content: space-between; padding: var(--ds-space-2) var(--ds-space-4); }
}
@container (max-width: 520px) {
  .pay-fees, .pay-wording { grid-template-columns: minmax(0, 1fr); }
  .pay-fee-hint { min-height: 0; }
  /* Name and description get the full width; the approval badge and the switch sit on a line below. */
  .pay-head { flex-wrap: wrap; row-gap: var(--ds-space-3); padding: var(--ds-space-4); }
  .pay-name { flex: 1 1 100%; }
  .pay-switch { margin-left: auto; }
  .pay-body { padding: var(--ds-space-4); }
  .pay-savebar > span { flex: 1 1 100%; }
  .pay-savebar > :not(span) { flex: 1 1 0; }
}
</style>
