<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { currencyFor, phoneCountryFor } from '@/services/countryDefaults'
import AppRadioCard from '@/components/ui/AppRadioCard.vue'
import UploadBox from '@/components/ui/UploadBox.vue'
import { useAuthStore } from '@/stores/auth'
import { COUNTRY_CODES } from '@/data/countries'
import { ApiError, CURRENCIES, PHONE_COUNTRIES, platform, type LaunchPackageId, type ModuleInfo, type StarterSetInfo } from '@/services/platform'
import { MOCK_STARTER_SETS, allowedModules, startingModules } from '@/services/modulesCatalogue'
import { EVENT_PASS_DAYS, taxSplit, usd } from '@rootsquares/ui/mock/pricing'
import { loadPrices, minorOf } from '@/services/prices'
import { loadTaxRates, taxRates } from '@/services/taxRates'
import ModulesPicker from './ModulesPicker.vue'
import { THEMES } from '@rootsquares/ui/themes'
import { THEME_COLORS } from '@/themes/colors'
import ThemePreviewDialog from './ThemePreviewDialog.vue'
import VoucherField from '@/features/portal/VoucherField.vue'
import { savedReferral } from '@/services/referral'
import { errorText } from './errorText'
import { LOGO_ACCEPT, checkLogo } from './logoFile'

// Create square, step by step (W11-R39): plan, basics, look, region, modules, review. One page; the step is in the URL (?step=) so the browser's back button works; nothing is sent
// until the last step. The API answers 202 and provisions in the background.
const { t, te } = useI18n()
const router = useRouter()
const route = useRoute()
const name = ref('')
const slug = ref('')
const slugTouched = ref(false)
const queryTheme = String(route.query.theme ?? '')
const themeId = ref(THEMES.some((t) => t.id === queryTheme) ? queryTheme : THEMES[0]!.id)
const chosenTheme = computed(() => THEMES.find((x) => x.id === themeId.value) ?? THEMES[0]!)
const swatches = computed(() => { const c = THEME_COLORS[themeId.value]?.light; return c ? [c.bg, c.ink, c.accent] : [] })
const browseOpen = ref(false) // the theme browser opens on top of this form, so nothing typed here is lost
const browseId = ref(themeId.value)
function openBrowse() { browseId.value = themeId.value; browseOpen.value = true }
function useBrowsed() { themeId.value = browseId.value; browseOpen.value = false }
const currency = ref<string>('') // chosen once, when the square is created; no default, the owner must choose (W12-R11)
const auth = useAuthStore()
loadTaxRates()
const billingCountry = ref<string>(auth.user?.organizations[0]?.billing_country ?? '') // where the owner is: tax and invoices (W12-R12)
const phoneCountry = ref<string>('') // the same: which country's phone numbers its forms accept
// Choosing the owner's country suggests the currency and the phone country (W14-R31); either can still be changed, and then it is left alone
const currencyTouched = ref(false)
const phoneTouched = ref(false)
watch(billingCountry, (country) => {
  if (!country) return
  if (!currencyTouched.value) currency.value = currencyFor(country) || currency.value
  if (!phoneTouched.value) phoneCountry.value = phoneCountryFor(country, PHONE_COUNTRIES) || phoneCountry.value
}, { immediate: true })
const countryNames = new Intl.DisplayNames(['en'], { type: 'region' })
const logo = ref<File | null>(null) // optional; uploaded right after the square is created
const logoError = ref('')
const logoDark = ref<File | null>(null) // optional second logo for dark backgrounds
const logoDarkError = ref('')
const moduleList = ref<ModuleInfo[]>([])
const PACKAGES: LaunchPackageId[] = ['roots', 'square', 'grove', 'event']
const queryPackage = String(route.query.package ?? route.query.running ?? '')
// The launch package (W10-R40) decides which modules can be switched on; /pricing sends ?package=roots|square|grove, or ?running=event for the Event pass.
const pkg = ref<LaunchPackageId>((PACKAGES as string[]).includes(queryPackage) ? (queryPackage as LaunchPackageId) : 'square')
void loadPrices() // prices are data on the platform: nothing is written in the code (W14-R29); a price that is not set shows a dash
const priceOf = (id: LaunchPackageId) => { const m = minorOf(id === 'event' ? 'launch.event' : `launch.${id}`); return m === null ? '—' : usd(m) }
const allowed = computed(() => allowedModules(moduleList.value, pkg.value))
const chosenModules = ref<string[]>([]) // the starter set's modules are ticked (within the package); the owner can change them now or later
// The kind of group (W14-R10): each kind starts with its own modules. Cultural is what every square started with before; the server's list is used when it answers.
const starterSets = ref<StarterSetInfo[]>(MOCK_STARTER_SETS)
const groupType = ref<string>('cultural')
const starter = computed(() => starterSets.value.find((s) => s.key === groupType.value))
function resetModules() { chosenModules.value = startingModules(moduleList.value, pkg.value, starter.value) }
watch([pkg, groupType], resetModules)
onMounted(async () => {
  try {
    starterSets.value = await platform.listStarterSets()
  } catch { /* the built-in list is used */ }
  try {
    moduleList.value = await platform.listModules()
    resetModules()
  } catch { /* the form still works: the server then gives the starter set's modules */ }
})
const error = ref('')
const slugError = ref('')
const busy = ref(false)

const slugify = (s: string) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40)
watch(name, (v) => { if (!slugTouched.value) slug.value = slugify(v) })
const valid = computed(() => name.value.trim().length >= 2 && /^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$/.test(slug.value))
const regionOk = computed(() => !!currency.value && !!phoneCountry.value && !!billingCountry.value)

type StepId = 'plan' | 'basics' | 'kind' | 'look' | 'region' | 'modules' | 'review'
// The modules step has nothing to choose for Roots (none) and the Event pass (a fixed list), so it is left out.
// The kind-of-group step is left out for the Event pass too (one event: its own fixed list).
const stepIds = computed<StepId[]>(() => ['plan', 'basics', ...(pkg.value === 'event' || starterSets.value.length < 2 ? [] : ['kind' as const]), 'look', 'region', ...(moduleList.value.length && pkg.value !== 'event' && allowed.value.length ? ['modules' as const] : []), 'review'])
const firstStep: StepId = queryPackage ? 'basics' : 'plan' // arriving from Pricing, the plan is already chosen
const step = computed<StepId>(() => {
  const q = String(route.query.step ?? '') as StepId
  const id = stepIds.value.includes(q) ? q : firstStep
  // A reload loses what was typed: never show a later step with an empty name.
  if (!valid.value && stepIds.value.indexOf(id) > stepIds.value.indexOf('basics')) return 'basics'
  return !regionOk.value && stepIds.value.indexOf(id) > stepIds.value.indexOf('region') ? 'region' : id
})
const stepIndex = computed(() => stepIds.value.indexOf(step.value))
const stepTitle = (id: StepId) => t(`plat.create.step.${id}`)
const canNext = computed(() => (step.value !== 'basics' || valid.value) && (step.value !== 'region' || regionOk.value))
function goStep(id: StepId) { void router.push({ query: { ...route.query, step: id } }) }
function next() { const id = stepIds.value[stepIndex.value + 1]; if (id && canNext.value) goStep(id) }
function back() { const id = stepIds.value[stepIndex.value - 1]; if (id) goStep(id) }
function enter() { if (step.value === 'review') void submit(); else next() }
type ReviewRow = { label: string; value: string; note?: string; swatches?: string[]; none?: boolean }
// What the package keeps out (W15-R6): the modules it does not allow and, for Square, the two features that only Grove has.
const lockedRows = computed<ReviewRow[]>(() => {
  const names = moduleList.value.filter((m) => !allowed.value.includes(m.key)).map((m) => m.label)
  if (!names.length) return []
  const features = pkg.value === 'square' ? `; ${t('plat.create.reviewLockedFeatures')}` : ''
  return [{ label: t('plat.create.reviewLocked', { name: pkgName.value }), value: names.join(', ') + features, none: true }]
})
const reviewGroups = computed<{ id: string; title: string; step: StepId; rows: ReviewRow[] }[]>(() => {
  const none = t('plat.create.reviewNone')
  const country = (code: string) => (code ? (countryNames.of(code) ?? code) : '')
  return [
    { id: 'site', title: t('plat.create.secSite'), step: 'basics', rows: [
      { label: t('plat.create.name'), value: name.value.trim() },
      { label: t('plat.create.slug'), value: `${slug.value}.rootsquares.com` },
    ] },
    ...(stepIds.value.includes('kind')
      ? [{ id: 'kind', title: t('plat.create.secKind'), step: 'kind' as StepId, rows: [{ label: t('plat.create.secKind'), value: starter.value?.label ?? '' }] }]
      : []),
    { id: 'look', title: t('plat.create.secLook'), step: 'look', rows: [
      { label: t('plat.create.theme'), value: chosenTheme.value.name, note: chosenTheme.value.shellLabel, swatches: swatches.value },
      { label: t('plat.create.reviewLogoLight'), value: logo.value?.name ?? none, none: !logo.value },
      { label: t('plat.create.reviewLogoDark'), value: logoDark.value?.name ?? none, none: !logoDark.value },
    ] },
    { id: 'region', title: t('plat.create.secRegion'), step: 'region', rows: [
      { label: t('plat.create.billingCountry'), value: country(billingCountry.value) },
      { label: t('plat.create.currency'), value: currency.value },
      { label: t('plat.create.phoneCountry'), value: country(phoneCountry.value) },
    ] },
    ...(stepIds.value.includes('modules')
      ? [{ id: 'modules', title: t('plat.modules.title'), step: 'modules' as StepId, rows: [{ label: t('plat.modules.title'), value: t('plat.create.reviewModules', { n: chosenModules.value.length }) }, ...lockedRows.value] }]
      : []),
  ]
})
const pkgName = computed(() => (pkg.value === 'event' ? t('marketing.pricing.running.event.name') : t(`marketing.pricing.launch.${pkg.value}.name`)))
// An Event pass is paid at checkout right after Create; every other package starts free and its first payment (package plus the first Live month) comes later.
const dueMinor = computed<number | null>(() => {
  if (pkg.value === 'event') return minorOf('launch.event')
  const launch = minorOf(`launch.${pkg.value}`), month = minorOf('running.live.month')
  return launch === null || month === null ? null : launch + month
})
const taxPercent = computed(() => taxRates.value[billingCountry.value] ?? 0) // the tax inside the price for the chosen country (W13-R51)
const dueAmount = computed(() => (dueMinor.value === null ? '—' : usd(dueMinor.value)))

function chooseLogo(files: FileList | null) {
  const file = files?.[0]
  if (!file) return
  const problem = checkLogo(file)
  logoError.value = problem ? t(problem === 'type' ? 'plat.create.logoType' : 'plat.create.logoSize') : ''
  logo.value = problem ? null : file
}

function chooseLogoDark(files: FileList | null) {
  const file = files?.[0]
  if (!file) return
  const problem = checkLogo(file)
  logoDarkError.value = problem ? t(problem === 'type' ? 'plat.create.logoType' : 'plat.create.logoSize') : ''
  logoDark.value = problem ? null : file
}

const voucherCode = ref(savedReferral()) // asked on the review step for every package (W14-R27, W14-R30): an Event pass takes it to checkout, a launch package keeps it for the first payment
const checkVoucher = (code: string) => platform.voucherPreview({ code, kind: pkg.value === 'event' ? 'event_pass' : 'first', launch_package: pkg.value === 'event' ? undefined : pkg.value })
const voucherError = ref('') // a refused code is told inside the payment card, next to the box, not in a banner at the top
watch(voucherCode, () => { voucherError.value = '' })
async function submit() {
  error.value = slugError.value = voucherError.value = ''
  busy.value = true
  try {
    if (pkg.value === 'event' && voucherCode.value.trim()) {
      // an Event pass is created before it is paid, so the code is checked first: a wrong one must not leave a square behind
      const check = await checkVoucher(voucherCode.value.trim())
      if (!check.valid) { voucherError.value = (check.reason && te(`plat.errors.${check.reason}`) ? t(`plat.errors.${check.reason}`) : check.message) ?? t('plat.errors.generic'); return }
    }
    const sq = await platform.createSquare({ name: name.value.trim(), slug: slug.value, theme_id: themeId.value, currency: currency.value, phone_country: phoneCountry.value, billing_country: billingCountry.value, modules: moduleList.value.length ? chosenModules.value : undefined, launch_package: pkg.value, group_type: pkg.value === 'event' ? undefined : groupType.value, voucher_code: pkg.value !== 'event' && voucherCode.value.trim() ? voucherCode.value.trim() : undefined })
    // The square exists now; a logo that fails to upload can be added on its page, so it never blocks the way there.
    if (logo.value) await platform.uploadSquareLogo(sq.id, logo.value).catch(() => undefined)
    if (logoDark.value) await platform.uploadSquareLogo(sq.id, logoDark.value, 'dark').catch(() => undefined)
    if (sq.awaiting_payment) {
      // An Event pass is paid before it is built (W12-R6): on to checkout; if the owner backs out, the square's Billing page offers it again.
      const { url } = await platform.startCheckout(sq.id, voucherCode.value.trim() ? { kind: 'event_pass', voucher_code: voucherCode.value.trim() } : { kind: 'event_pass' })
      window.location.assign(url)
      return
    }
    await router.push(`/squares/${sq.id}`)
  } catch (e) {
    if (e instanceof ApiError && (e.code === 'slug_taken' || e.code === 'slug_reserved')) { slugError.value = errorText(t, e); goStep('basics') }
    else if (e instanceof ApiError && (e.code.startsWith('voucher_') || e.code === 'price_not_set') && voucherCode.value.trim()) voucherError.value = errorText(t, e)
    else error.value = errorText(t, e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="mk-sec"><div class="au-col" :class="step === 'review' && 'cr-wide'">
    <RouterLink to="/dashboard" class="bs-mute" style="font-size: var(--text-sm)">← {{ t('plat.detail.back') }}</RouterLink>
    <header style="display: grid; gap: 12px">
      <h1 class="bs-d" style="font-size: 40px">{{ t('plat.create.title') }}</h1>
      <hr class="rs-rule">
      <p class="bs-lede" style="font-size: var(--text-base)">{{ t('plat.create.lede') }}</p>
    </header>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
    <ol class="cr-steps" :aria-label="t('plat.create.stepsLabel')">
      <li v-for="(id, i) in stepIds" :key="id" :class="[i < stepIndex && 'done', id === step && 'on']" :aria-current="id === step ? 'step' : undefined"><b><AppIcon v-if="i < stepIndex" name="check" :size="12" :stroke-width="3" />{{ i < stepIndex ? '' : i + 1 }}</b>{{ stepTitle(id) }}</li>
    </ol>
    <p v-if="step !== 'review'" class="bs-mute" style="margin: 0; font-size: var(--text-sm)" role="status">{{ t('plat.create.stepOf', { n: stepIndex + 1, total: stepIds.length }) }}</p>
    <form :class="step === 'review' ? 'cr-grid' : 'rs-stack'" :style="step === 'review' ? undefined : 'gap: 16px'" novalidate @submit.prevent="enter">
      <template v-if="step === 'plan'">
        <div style="display: grid; gap: 6px" role="radiogroup" :aria-label="t('plat.create.package')">
          <span class="rs-label">{{ t('plat.create.package') }}</span>
          <p class="bs-mute" style="margin: 0">{{ t('plat.create.packageLede') }}</p>
          <AppRadioCard v-for="id in PACKAGES" :key="id" v-model="pkg" :value="id" :title="`${id === 'event' ? t('marketing.pricing.running.event.name') : t(`marketing.pricing.launch.${id}.name`)} · ${priceOf(id)}`" :hint="id === 'event' ? t('plat.create.eventHint', { days: EVENT_PASS_DAYS }) : t(`marketing.pricing.launch.${id}.text`)" />
          <small class="bs-mute">{{ t('plat.create.packageNote') }}</small>
          <a href="/pricing" target="_blank" rel="noopener" style="font-size: var(--text-sm)">{{ t('plat.create.comparePlans') }}</a>
        </div>
      </template>
      <template v-else-if="step === 'basics'">
        <AppField v-model="name" :label="t('plat.create.name')" :placeholder="t('plat.create.namePh')" />
        <AppField v-model="slug" :label="t('plat.create.slug')" suffix=".rootsquares.com" :hint="t('plat.create.slugHint')" :error="slugError" @update:model-value="slugTouched = true" />
      </template>
      <template v-else-if="step === 'kind'">
        <div style="display: grid; gap: 6px" role="radiogroup" :aria-label="t('plat.create.kind')">
          <span class="rs-label">{{ t('plat.create.kind') }}</span>
          <p class="bs-mute" style="margin: 0">{{ t('plat.create.kindLede') }}</p>
          <AppRadioCard v-for="s in starterSets" :key="s.key" v-model="groupType" :value="s.key" :title="s.label" :hint="s.description" />
          <small class="bs-mute">{{ t('plat.create.kindNote') }}</small>
        </div>
      </template>
      <template v-else-if="step === 'look'">
        <div style="display: grid; gap: 6px">
          <span class="rs-label">{{ t('plat.create.theme') }}</span>
          <div class="bs-row" style="gap: 12px; align-items: center; flex-wrap: wrap">
            <i class="tp-sw"><b v-for="c in swatches" :key="c" :style="{ background: c }" /></i>
            <select v-model="themeId" class="rs-input" :aria-label="t('portal.theme.pickLabel')" style="width: 260px; max-width: 100%"><option v-for="x in THEMES" :key="x.id" :value="x.id">{{ x.name }}</option></select>
            <AppButton variant="secondary" icon="eye" @click="openBrowse">{{ t('plat.create.themeChange') }}</AppButton>
          </div>
          <small class="bs-mute" style="font-size: var(--text-xs)">{{ chosenTheme.shellLabel }} · {{ chosenTheme.colour }}</small>
          <small class="bs-mute">{{ t('plat.create.themeHint') }}</small>
        </div>
        <div style="display: grid; gap: 6px">
          <span class="rs-label">{{ t('plat.create.logo') }}</span>
          <UploadBox kind="file" :state="logoError ? 'error' : logo ? 'preview' : 'default'" :accept="LOGO_ACCEPT" :name="logo?.name" :meta="logo ? `${Math.ceil(logo.size / 1000)} KB` : ''" :error-text="logoError" :prompt="t('plat.create.logoPrompt')" :hint="t('plat.create.logoHint')" @choose="chooseLogo" @remove="logo = null" />
        </div>
        <div style="display: grid; gap: 6px">
          <span class="rs-label">{{ t('plat.create.logoDark') }}</span>
          <UploadBox kind="file" :state="logoDarkError ? 'error' : logoDark ? 'preview' : 'default'" :accept="LOGO_ACCEPT" :name="logoDark?.name" :meta="logoDark ? `${Math.ceil(logoDark.size / 1000)} KB` : ''" :error-text="logoDarkError" :prompt="t('plat.create.logoPrompt')" :hint="t('plat.create.logoDarkHint')" @choose="chooseLogoDark" @remove="logoDark = null" />
        </div>
      </template>
      <template v-else-if="step === 'region'">
        <AppField v-model="billingCountry" as="select" :label="t('plat.create.billingCountry')" :options="[{ value: '', label: t('plat.create.choose') }, ...COUNTRY_CODES.map((c) => ({ value: c, label: countryNames.of(c) ?? c })).sort((a, b) => a.label.localeCompare(b.label))]" :hint="t('plat.create.billingCountryHint')" />
        <AppField v-model="currency" as="select" @update:model-value="currencyTouched = true" :label="t('plat.create.currency')" :options="[{ value: '', label: t('plat.create.choose') }, ...CURRENCIES.map((c) => ({ value: c, label: c }))]" :hint="t('plat.create.currencyHint')" />
        <AppField v-model="phoneCountry" as="select" @update:model-value="phoneTouched = true" :label="t('plat.create.phoneCountry')" :options="[{ value: '', label: t('plat.create.choose') }, ...PHONE_COUNTRIES.map((c) => ({ value: c, label: countryNames.of(c) ?? c }))]" :hint="t('plat.create.phoneCountryHint')" />
      </template>
      <template v-else-if="step === 'modules'">
        <div style="display: grid; gap: 6px">
          <span class="rs-label">{{ t('plat.modules.title') }}</span>
          <p class="bs-mute" style="margin: 0">{{ t('plat.modules.lede') }}</p>
          <ModulesPicker v-model="chosenModules" :modules="moduleList" :allowed="allowed" :launch-package="pkg" :recommended="starter?.modules" :kind-label="starter?.label" />
        </div>
      </template>
      <template v-else>
        <div class="cr-main">
          <p class="cr-eb">{{ t('plat.create.stepOf', { n: stepIndex + 1, total: stepIds.length }) }}</p>
          <h2 class="cr-h2">{{ t('plat.create.reviewTitle') }}</h2>
          <section v-for="g in reviewGroups" :key="g.id" class="cr-sec">
            <div class="cr-sh"><b>{{ g.title }}</b><a href="#" @click.prevent="goStep(g.step)">{{ t('plat.create.edit') }}</a></div>
            <dl>
              <div v-for="r in g.rows" :key="r.label" class="cr-r">
                <dt>{{ r.label }}</dt>
                <dd :class="[r.none && 'cr-mut', r.swatches?.length && 'cr-dd']"><i v-if="r.swatches?.length" class="tp-sw cr-pad"><b v-for="c in r.swatches" :key="c" :style="{ background: c }" /></i><span><span>{{ r.value }}</span><span v-if="r.note" class="cr-mut"> · {{ r.note }}</span></span></dd>
              </div>
            </dl>
          </section>
        </div>
        <aside class="cr-aside">
          <p class="cr-eb">{{ t('plat.create.package') }}</p>
          <p class="cr-pk">{{ pkgName }}</p>
          <span class="cr-u">{{ slug }}.rootsquares.com</span>
          <a href="#" class="cr-change" @click.prevent="goStep('plan')">{{ t('plat.create.changePlan') }}</a>
          <div class="cr-tot"><span>{{ pkg === 'event' ? t('plat.create.total') : t('plat.create.firstPayment') }}</span><b>{{ dueAmount }}</b></div>
          <p v-if="taxPercent > 0 && dueMinor !== null" class="cr-note">{{ t('tax.included', { percent: taxPercent, net: usd(taxSplit(dueMinor, taxPercent).net), tax: usd(taxSplit(dueMinor, taxPercent).tax) }) }}</p>
          <p class="cr-note">{{ pkg === 'event' ? t('plat.create.noteEvent') : t('plat.create.noteTrial') }}</p>
          <VoucherField v-model="voucherCode" :check="checkVoucher" :error="voucherError" style="margin: 12px 0" />
          <button type="submit" class="cr-btn cr-p" :disabled="busy || !valid || !regionOk">{{ busy ? t('plat.create.busy') : t('plat.create.submit') }}</button>
          <button type="button" class="cr-btn cr-g" @click="back">{{ t('plat.create.back') }}</button>
          <RouterLink to="/dashboard" class="cr-c">{{ t('common.cancel') }}</RouterLink>
        </aside>
      </template>
      <div v-if="step !== 'review'" class="bs-row" style="gap: 10px; flex-wrap: wrap">
        <AppButton v-if="stepIndex > 0" icon="chevron-left" variant="secondary" @click="back">{{ t('plat.create.back') }}</AppButton>
        <AppButton icon="arrow" type="submit" :disabled="!canNext">{{ t('plat.create.next') }}</AppButton>
        <AppButton icon="x" variant="ghost" to="/dashboard">{{ t('common.cancel') }}</AppButton>
      </div>
    </form>
    <ThemePreviewDialog v-if="browseOpen" v-model:theme-id="browseId" :themes="THEMES" :name="name.trim() || t('plat.create.title')" can-apply :apply-label="t('plat.create.themeUse')" @apply="useBrowsed" @close="browseOpen = false" />
  </div></section>
</template>
