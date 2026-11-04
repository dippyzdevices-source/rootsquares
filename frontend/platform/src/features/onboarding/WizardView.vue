<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppCheck from '@rootsquares/ui/components/AppCheck.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import CopyField from '@/components/ui/CopyField.vue'
import StepperRail from '@/components/ui/StepperRail.vue'
import SwitchBtn from '@/components/ui/SwitchBtn.vue'
import Wordmark from '@rootsquares/ui/components/Wordmark.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { checkDomain, launchSite } from '@/services/api'
import { MOCK_MODULES, completeModules, recommendedModules, withoutModule } from '@/services/modulesCatalogue'
import { DOMAIN_RECORDS } from '@/mock/placeholders'
import { useTenantStore } from '@/stores/tenant'
import { useUiStore } from '@rootsquares/ui/stores/ui'
import { THEMES } from '@rootsquares/ui/themes'
import { THEME_COLORS } from '@/themes/colors'
import ThemeFilterBar from '@/features/platform/ThemeFilterBar.vue'
import ThemeComingList from '@/features/platform/ThemeComingList.vue'
import ThemePreviewPane from '@/features/platform/ThemePreviewPane.vue'
import { useThemeFilter } from '@/features/platform/themeFilter'

// Onboarding wizard, design v4 (screens/H.jsx, export/screens.md "Onboarding wizard (shared shell)"): six steps (Account, Name and address, Theme,
// Modules, Domain, Review), then "Your site is live". Wide: 268px rail + content pane (max 640px; Theme step full width) + footer Back / Continue.
// Narrow: 2px brass progress bar and "n / 6". This is the clickable prototype on mock data: nothing is created (the real flow is Sign up, then
// Create square). Only the states that can happen here are built (duplicate email, domain verifying and not found, launch failed).
const { t } = useI18n()
const tenant = useTenantStore()
const ui = useUiStore()
const { push } = useToast()

const LAST = 5
const stepIds = ['account', 'name', 'theme', 'modules', 'domain', 'review'] as const
const steps = computed(() => stepIds.map((s) => t(`wizard.steps.${s}`)))
const i = ref(0)
const touched = ref(false)
const live = ref(false)

// 1 Account
const account = ref({ name: '', email: '', password: '' })
const creating = ref(false)
const duplicate = ref(false)
const emailOk = computed(() => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(account.value.email))
// 2 Name and address
const name = ref('')
const addressTouched = ref(false)
const addressEdit = ref('')
const type = ref('cultural')
const slugOf = (v: string) => v.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
const address = computed(() => (addressTouched.value ? addressEdit.value : slugOf(name.value)))
const addressOk = computed(() => /^[a-z0-9]+(-[a-z0-9]+)*$/.test(address.value))
const SUFFIX = '.rootsquares.com'
// 3 Theme
const themeId = ref(THEMES[0]!.id)
const { q: themeQ, shell: themeShell, filtered: themesShown, counts: themeCounts, coming: themesComing } = useThemeFilter()
const darkPreview = ref(false)
// 4 Modules
const modules = ref<string[]>(recommendedModules(MOCK_MODULES))
const setModule = (key: string, on: boolean) => { modules.value = on ? completeModules(MOCK_MODULES, [...modules.value, key]) : withoutModule(MOCK_MODULES, modules.value, key) }
// 5 Domain
const ownDomain = ref('')
const domainState = ref<'pending' | 'verifying' | 'live' | 'error'>('pending')
const domainOk = computed(() => /^[a-z0-9-]+(\.[a-z0-9-]+)+$/i.test(ownDomain.value.trim()))
const hasOwn = computed(() => !!ownDomain.value.trim())
// 6 Review and launch
const launching = ref(false)
const launchFailed = ref(false)
const launchStep = ref(0) // 0 queued, 1..3 working on step n, 4 all done

const finalDomain = computed(() => (hasOwn.value && domainState.value === 'live' ? ownDomain.value.trim() : address.value + SUFFIX))
const theme = computed(() => THEMES.find((x) => x.id === themeId.value)!)
const moduleNames = computed(() => MOCK_MODULES.filter((m) => modules.value.includes(m.key)).map((m) => m.label).join(', ') || t('wizard.review.none'))

const errors = computed(() => ({
  aName: touched.value && i.value === 0 && !account.value.name.trim() ? t('wizard.account.fieldRequired') : '',
  aEmail: duplicate.value ? t('wizard.account.dupField') : touched.value && i.value === 0 && !emailOk.value ? t('wizard.account.fieldRequired') : '',
  aPassword: touched.value && i.value === 0 && account.value.password.length < 10 ? t('wizard.account.passwordShort') : '',
  name: touched.value && i.value === 1 && !name.value.trim() ? t('wizard.name.nameError') : '',
  address: touched.value && i.value === 1 && !!name.value.trim() && !addressOk.value ? t('wizard.name.addressError') : '',
  domain: touched.value && i.value === 4 && hasOwn.value && !domainOk.value ? t('wizard.domain.ownError') : '',
}))
const valid = computed(() => {
  if (i.value === 0) return !!account.value.name.trim() && emailOk.value && account.value.password.length >= 10
  if (i.value === 1) return !!name.value.trim() && addressOk.value
  if (i.value === 4) return !hasOwn.value || domainOk.value
  return true
})

function go(n: number) { i.value = Math.max(0, Math.min(LAST, n)); touched.value = false; window.scrollTo({ top: 0 }) }
async function next() {
  if (!valid.value) { touched.value = true; return }
  if (i.value === 0) {
    duplicate.value = false
    creating.value = true
    await new Promise((r) => setTimeout(r, 600))
    creating.value = false
    if (account.value.email.trim().toLowerCase() === 'taken@example.com') { duplicate.value = true; return }
  }
  go(i.value + 1)
}

const swatch = (id: string) => { const c = THEME_COLORS[id]![ui.mode]; return [c.bg, c.ink, c.accent] }

async function verify() {
  domainState.value = 'verifying'
  try { await checkDomain(); domainState.value = 'live' } catch { domainState.value = 'error' }
}
const domainRecords = DOMAIN_RECORDS.filter((r) => r.type !== 'A')

async function launch() {
  launching.value = true
  launchFailed.value = false
  launchStep.value = 1
  try {
    const tick = (n: number) => new Promise<void>((r) => setTimeout(() => { launchStep.value = n; r() }, 450))
    await tick(1)
    await launchSite()
    await tick(2)
    await tick(3)
    await tick(4)
  } catch {
    launching.value = false
    launchFailed.value = true
    launchStep.value = 0
    return
  }
  tenant.applyWizard({ name: name.value.trim(), themeId: themeId.value, modules: modules.value, domainMode: hasOwn.value ? 'own' : 'sub', domain: finalDomain.value, logoName: '', accent: THEME_COLORS[themeId.value]!.light.accent })
  launching.value = false
  live.value = true
  push(t('wizard.live.launched'), 'success')
  window.scrollTo({ top: 0 })
}
const stepState = (n: number) => (launchStep.value === 0 ? '' : launchStep.value > n ? 'ok' : launchStep.value === n ? 'cur' : '')
const url = computed(() => `https://${finalDomain.value}`)
const adminUrl = computed(() => `${url.value}/admin`) // the square's own admin, the real one (W23-R82)
const mailto = computed(() => `mailto:?subject=${encodeURIComponent(t('wizard.live.mailSubject'))}&body=${encodeURIComponent(url.value)}`)
const facebook = computed(() => `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url.value)}`)
const review = computed(() => [
  { k: 'rName', v: name.value, step: 1 },
  { k: 'rAddress', v: address.value + SUFFIX, step: 1 },
  { k: 'rTheme', v: theme.value.name, step: 2 },
  { k: 'rModules', v: moduleNames.value, step: 3 },
  { k: 'rDomain', v: hasOwn.value ? `${ownDomain.value.trim()} · ${t(`wizard.domain.${domainState.value}`)}` : t('wizard.review.freeAddress'), step: 4 },
])
</script>

<template>
  <div class="bw-shell">
    <template v-if="!live">
      <div class="bw-mtop bs-top bs-top--m"><Wordmark :size="20" /><span class="bs-sp" /><span class="bs-mute" style="font-size: var(--text-xs)">{{ i + 1 }} / 6</span></div>
      <div class="bw-mprog bs-prog" role="progressbar" :aria-label="t('wizard.progress')" :aria-valuenow="i + 1" aria-valuemin="1" aria-valuemax="6"><i :style="{ width: ((i + 1) / 6) * 100 + '%' }" /></div>
      <div class="bs-wiz">
        <StepperRail :steps="steps" :current="i"><template #foot><RouterLink to="/" style="font-size: var(--text-sm)">{{ t('wizard.saveExit') }}</RouterLink></template></StepperRail>
        <div class="bw-pane">
          <div class="bw-body" :style="i === 2 ? undefined : { maxWidth: '640px' }">
            <div class="bw-hd">
              <span class="rs-eyebrow">{{ t('wizard.eyebrow', { n: i + 1 }) }}</span>
              <h1 style="font-size: 1.75rem">{{ t(`wizard.${stepIds[i]}.title`) }}</h1>
              <p class="bs-mute" style="margin: 0; font-size: var(--text-sm)">{{ t(`wizard.${stepIds[i]}.text`, { address: address + SUFFIX }) }}</p>
            </div>

            <!-- 1 Account -->
            <template v-if="i === 0">
              <AppAlert v-if="duplicate" tone="danger" :title="t('wizard.account.dupTitle')">{{ t('wizard.account.dupText') }}</AppAlert>
              <AppField v-model="account.name" :label="t('wizard.account.name')" autocomplete="name" :error="errors.aName" />
              <AppField v-model="account.email" type="email" :label="t('wizard.account.email')" autocomplete="email" :error="errors.aEmail" />
              <AppField v-model="account.password" type="password" :label="t('wizard.account.password')" autocomplete="new-password" :hint="t('wizard.account.passwordHint')" :error="errors.aPassword" />
              <i18n-t keypath="wizard.account.terms" tag="span" class="bs-mute" style="font-size: var(--text-xs)">
                <template #terms><a href="#" @click.prevent>{{ t('wizard.account.termsLink') }}</a></template>
                <template #privacy><a href="#" @click.prevent>{{ t('wizard.account.privacyLink') }}</a></template>
              </i18n-t>
            </template>

            <!-- 2 Name and address -->
            <template v-else-if="i === 1">
              <AppField v-model="name" :label="t('wizard.name.name')" autocomplete="organization" :error="errors.name" />
              <AppField :model-value="address" :label="t('wizard.name.address')" :suffix="SUFFIX" :hint="t('wizard.name.addressHint')" :error="errors.address" autocomplete="off" @update:model-value="(v) => { addressTouched = true; addressEdit = v }" />
              <fieldset class="rs-field" style="border: 0; padding: 0; margin: 0">
                <legend class="rs-label">{{ t('wizard.name.type') }}</legend>
                <div style="display: grid; gap: 8px">
                  <AppCheck v-for="k in ['cultural', 'religious', 'language', 'other']" :key="k" v-model="type" type="radio" name="group-type" :value="k" :label="t(`wizard.name.types.${k}[0]`)" :description="t(`wizard.name.types.${k}[1]`)" />
                </div>
              </fieldset>
            </template>

            <!-- 3 Theme -->
            <div v-else-if="i === 2" class="bw-two">
              <div class="bw-themes" role="group" :aria-label="t('wizard.theme.group')">
                <ThemeFilterBar v-model:q="themeQ" v-model:shell="themeShell" :shown="themesShown.length" :counts="themeCounts" />
                <div class="bw-themes" style="max-height: 440px; overflow-y: auto">
                  <p v-if="!themesShown.length" class="bs-mute" style="font-size: var(--text-sm)">{{ t('themes.none') }}</p>
                  <button v-for="th in themesShown" :key="th.id" type="button" class="bw-th" :aria-pressed="themeId === th.id" @click="themeId = th.id">
                    <i><b v-for="c in swatch(th.id)" :key="c" :style="{ background: c }" /></i>
                    <span><b style="font-weight: 500">{{ th.name }}</b><small>{{ th.shellLabel }} · {{ th.colour }}</small></span>
                  </button>
                  <ThemeComingList :themes="themesComing" />
                </div>
                <div class="bs-row" style="justify-content: space-between; padding-top: 6px; min-height: 44px"><span style="font-size: var(--text-sm)">{{ t('wizard.theme.darkPreview') }}</span><SwitchBtn v-model="darkPreview" :label="t('wizard.theme.darkPreview')" /></div>
              </div>
              <ThemePreviewPane :theme="theme" :name="name || t('wizard.theme.sample')" :mode="darkPreview ? 'dark' : 'light'" :sketch-zoom="1.3" />
            </div>

            <!-- 4 Modules -->
            <template v-else-if="i === 3">
              <div class="bw-sum" style="padding: 0 14px" role="group" :aria-label="t('wizard.steps.modules')">
                <div v-for="m in MOCK_MODULES" :key="m.key" class="bw-mod">
                  <b>{{ m.label }}</b><small>{{ m.description }}</small>
                  <span class="sw"><SwitchBtn :model-value="modules.includes(m.key)" :label="m.label" @update:model-value="(on) => setModule(m.key, on)" /></span>
                </div>
              </div>
              <span class="bs-mute" style="font-size: var(--text-xs)" aria-live="polite">{{ t('wizard.modules.count', { n: modules.length, total: MOCK_MODULES.length }) }}</span>
            </template>

            <!-- 5 Domain -->
            <template v-else-if="i === 4">
              <AppField v-model="ownDomain" :label="t('wizard.domain.own')" :hint="t('wizard.domain.ownHint')" :error="errors.domain" placeholder="nordlys.no" autocomplete="off" @update:model-value="domainState = 'pending'" />
              <template v-if="hasOwn && domainOk">
                <div class="bs-row" style="justify-content: space-between; flex-wrap: wrap">
                  <b style="font-weight: 500">{{ ownDomain.trim() }}</b>
                  <span v-if="domainState === 'live'" class="rs-chip rs-chip--success"><AppIcon name="check" :size="12" />{{ t('wizard.domain.live') }}</span>
                  <span v-else-if="domainState === 'error'" class="rs-chip rs-chip--danger"><AppIcon name="alert" :size="12" />{{ t('wizard.domain.error') }}</span>
                  <span v-else-if="domainState === 'verifying'" class="rs-chip rs-chip--info"><span class="bw-spin" />{{ t('wizard.domain.verifying') }}</span>
                  <span v-else class="rs-chip rs-chip--warning"><AppIcon name="clock" :size="12" />{{ t('wizard.domain.pending') }}</span>
                </div>
                <AppAlert v-if="domainState === 'error'" tone="danger" :title="t('wizard.domain.errTitle')">{{ t('wizard.domain.errText') }}</AppAlert>
                <AppAlert v-if="domainState === 'live'" tone="success" :title="t('wizard.domain.liveTitle', { domain: ownDomain.trim() })">{{ t('wizard.domain.liveText') }}</AppAlert>
                <div v-if="domainState !== 'live'" style="display: grid; gap: 12px">
                  <div v-for="r in domainRecords" :key="r.name" style="display: grid; gap: 6px">
                    <div class="bx-cap">{{ t('wizard.domain.record', { type: r.type, host: r.name }) }}</div>
                    <CopyField :value="r.value" :label="t('wizard.domain.copy', { type: r.type })" />
                  </div>
                </div>
                <div v-if="domainState !== 'live'" class="bs-row" style="flex-wrap: wrap">
                  <AppButton icon="refresh" variant="secondary" :disabled="domainState === 'verifying'" style="min-height: 44px" @click="verify">{{ domainState === 'verifying' ? t('wizard.domain.checking') : domainState === 'error' ? t('wizard.domain.verifyAgain') : t('wizard.domain.verify') }}</AppButton>
                </div>
              </template>
            </template>

            <!-- 6 Review and launch -->
            <template v-else>
              <AppAlert v-if="launchFailed" tone="danger" :title="t('wizard.review.errTitle')">
                {{ t('wizard.review.errText') }}
                <template #action><AppButton icon="refresh" variant="secondary" size="sm" @click="launch">{{ t('wizard.review.retry') }}</AppButton></template>
              </AppAlert>
              <div class="bw-sum">
                <div v-for="r in review" :key="r.k" class="bw-sr"><span>{{ t(`wizard.review.${r.k}`) }}</span><span style="overflow-wrap: anywhere">{{ r.v }}</span><a href="#" @click.prevent="go(r.step)">{{ t('wizard.edit') }}</a></div>
              </div>
              <div class="bw-steps" aria-live="polite">
                <div v-for="(s, n) in ['s1', 's2', 's3']" :key="s" class="bw-st" :class="stepState(n + 1)">
                  <i><AppIcon v-if="stepState(n + 1) === 'ok'" name="check" :size="12" /><span v-else-if="stepState(n + 1) === 'cur'" class="bw-spin" /><template v-else>{{ n + 1 }}</template></i>
                  {{ t(`wizard.review.${s}`) }}
                  <span class="bs-mute" style="font-size: var(--text-xs)">{{ stepState(n + 1) === 'ok' ? t('wizard.review.done') : stepState(n + 1) === 'cur' ? t('wizard.review.working') : t('wizard.review.queued') }}</span>
                </div>
              </div>
              <p class="bs-mute" style="margin: 0; font-size: var(--text-xs)">{{ t('wizard.review.trial') }}</p>
            </template>
          </div>
          <div style="flex: 1" />
          <div class="bs-wf">
            <AppButton v-if="i > 0" icon="chevron-left" variant="ghost" :disabled="launching || creating" style="min-height: 44px" @click="go(i - 1)">{{ t('wizard.back') }}</AppButton><span v-else />
            <AppButton v-if="i < LAST" icon="plus" :disabled="creating" :loading="creating" style="min-height: 44px" @click="next">{{ i === 0 ? (creating ? t('wizard.account.creating') : t('wizard.account.create')) : i === 4 && !(hasOwn && domainState === 'live') ? t('wizard.skip') : t('wizard.continue') }}</AppButton>
            <AppButton v-else size="lg" icon="sparkle" :disabled="launching" :loading="launching" style="min-height: 44px" @click="launch">{{ launching ? t('wizard.review.launching') : t('wizard.review.launch') }}</AppButton>
          </div>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="bs-top"><Wordmark :size="20" /><span class="bs-sp" /><a :href="adminUrl" target="_blank" rel="noopener" style="font-size: var(--text-sm)">{{ t('wizard.live.goConsole') }}</a></div>
      <main id="main" style="flex: 1; display: grid; align-content: center">
        <div class="bw-live">
          <span class="bw-seal"><AppIcon name="check" :size="24" /></span>
          <span class="rs-eyebrow">{{ t('wizard.live.eyebrow') }}</span>
          <h1>{{ t('wizard.live.title') }} <em>{{ t('wizard.live.em') }}</em></h1>
          <hr class="rs-rule">
          <p class="bs-mute" style="margin: 0">{{ t('wizard.live.text', { name }) }}</p>
          <div class="bw-share">
            <CopyField :value="url" :label="t('wizard.live.share')" />
            <div class="bw-sh">
              <AppButton icon="mail" variant="secondary" :href="mailto" style="min-height: 44px">{{ t('wizard.live.email') }}</AppButton>
              <AppButton icon="link" variant="secondary" :href="facebook" external style="min-height: 44px">{{ t('wizard.live.facebook') }}</AppButton>
              <AppButton icon="grid" variant="secondary" style="min-height: 44px" @click="push(t('wizard.live.qrSoon'), 'info', t('wizard.live.qrSoonBody'))">{{ t('wizard.live.qr') }}</AppButton>
            </div>
          </div>
          <div class="bs-row" style="flex-wrap: wrap; justify-content: center">
            <AppButton size="lg" icon="arrow" :href="adminUrl" external>{{ t('wizard.live.console') }}</AppButton>
            <AppButton icon="external" size="lg" variant="secondary" :to="`/site/${themeId}`">{{ t('wizard.live.visit') }}</AppButton>
          </div>
        </div>
      </main>
    </template>
  </div>
</template>
