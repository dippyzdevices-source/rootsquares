<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import DataRow from '@rootsquares/ui/components/DataRow.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { platform, type ModuleInfo, type ModuleStatus, type StarterSetInfo } from '@/services/platform'
import { MOCK_STARTER_SETS } from '@/services/modulesCatalogue'
import { errorText } from '@/features/platform/errorText'
import ModulesPicker from '@/features/platform/ModulesPicker.vue'
import { useSquare } from './squareContext'

// Modules page (design v4: "Modules page: switch list with Save modules"). A module that is off shows nowhere; its data is kept. Switching one off
// first reads the work in progress from the square (yes/no and plain sentences only, ADR 038) and asks the owner to confirm (warn, not block).
const { t } = useI18n()
const { push } = useToast()
const { sq, set } = useSquare()
const moduleList = ref<ModuleInfo[]>([])
const starterSets = ref<StarterSetInfo[]>(MOCK_STARTER_SETS)
// the Recommended group is the list of the square's kind of group (W15-R27); a square without a kind is a cultural group
const starter = computed(() => starterSets.value.find((s) => s.key === (sq.value?.group_type || 'cultural')))
const chosen = ref<string[]>([])
const status = ref<ModuleStatus[]>([])
const busy = ref(false)
const loading = ref(true)
const error = ref('')
const warnings = ref<string[]>([])
const warnOpen = ref(false)
// modules the package allows that are still off (from the saved list, so ticking boxes does not make the card come and go)
const offAllowed = computed(() => (sq.value ? sq.value.allowed_modules.filter((k) => !sq.value!.modules.includes(k)).length : 0))
const allOn = computed(() => !!sq.value && sq.value.allowed_modules.length > 0 && offAllowed.value === 0)
const packageName = computed(() => t(`marketing.pricing.launch.${sq.value?.launch_package}.name`, t('marketing.pricing.running.event.name')))
const changed = computed(() => !!sq.value && chosen.value.join() !== sq.value.modules.join())

async function loadStatus() {
  if (!sq.value) return
  try { status.value = (await platform.getModuleStatus(sq.value.id)).items } catch { status.value = [] }
}
async function load() {
  loading.value = true
  error.value = ''
  try { moduleList.value = await platform.listModules(); await loadStatus() } catch (e) { error.value = errorText(t, e) }
  try { starterSets.value = await platform.listStarterSets() } catch { /* the built-in lists stay */ }
  loading.value = false
}
watch(sq, (v) => { if (v && !busy.value) chosen.value = [...v.modules] }, { immediate: true })
onMounted(load)

async function save() {
  if (!sq.value) return
  const removed = sq.value.modules.filter((k) => !chosen.value.includes(k))
  if (removed.length) {
    busy.value = true
    await loadStatus() // fresh, not the picture from when the page opened
    busy.value = false
    const labels = new Map(moduleList.value.map((m) => [m.key, m.label]))
    const list = status.value.filter((s) => removed.includes(s.key)).flatMap((s) => s.pending.map((p) => `${labels.get(s.key) ?? s.key}: ${p}`))
    if (list.length) { warnings.value = list; warnOpen.value = true; return }
  }
  await doSave()
}
async function confirmOff() { warnOpen.value = false; await doSave() }
async function doSave() {
  if (!sq.value) return
  busy.value = true
  try {
    set(await platform.setSquareModules(sq.value.id, chosen.value))
    chosen.value = [...sq.value.modules]
    push(t('plat.modules.saved'), 'success')
    await loadStatus()
  } catch (e) {
    push(t('portal.modules.saveFailed'), 'danger', errorText(t, e))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <template v-if="sq">
    <div class="bw-hd"><h2 class="bs-h2" style="font-size: 28px">{{ t('plat.modules.title') }}</h2><p class="bs-mute" style="margin: 0; font-size: var(--text-sm)">{{ t('plat.modules.detailLede') }}</p></div>
    <AppAlert v-if="sq.status !== 'ready'" tone="info">{{ t('portal.modules.notReady') }}</AppAlert>
    <div v-else-if="loading" class="bx-list" aria-busy="true"><DataRow v-for="i in 4" :key="i" loading /></div>
    <AppAlert v-else-if="error" tone="danger" :title="t('bx.errorTitle')">
      {{ error }}
      <template #action><button type="button" class="rs-btn rs-btn--secondary rs-btn--sm" @click="load"><AppIcon name="refresh" :size="14" />{{ t('bx.retry') }}</button></template>
    </AppAlert>
    <template v-else>
      <p class="bs-mute" style="margin: 0; font-size: var(--text-sm)"><b style="font-weight: 500; color: var(--color-text)">{{ t('plat.modules.package') }}: {{ t(`marketing.pricing.launch.${sq.launch_package}.name`, t('marketing.pricing.running.event.name')) }}</b> · {{ t('plat.modules.packageLede') }}</p>
      <AppAlert v-if="offAllowed > 0" tone="info" :title="t('plat.modules.offTitle', { package: packageName, count: offAllowed }, offAllowed)">{{ t('plat.modules.offBody') }}</AppAlert>
      <AppAlert v-else-if="allOn" tone="success" :title="t('plat.modules.allOnTitle', { package: packageName })">{{ t('plat.modules.allOnBody', { count: sq.allowed_modules.length }) }}</AppAlert>
      <ModulesPicker v-model="chosen" :modules="moduleList" :status="status" :disabled="busy" :allowed="sq.allowed_modules" :launch-package="sq.launch_package" :recommended="starter?.modules" :kind-label="starter?.label" :upgrade-to="`/squares/${sq.id}/billing`" />
      <p v-if="sq.allowed_modules.length < moduleList.length" class="bs-mute" style="margin: 0; font-size: var(--text-xs)">{{ t('plat.modules.packageUpgrade') }} <RouterLink :to="`/squares/${sq.id}/billing`">{{ t('plat.modules.packageUpgradeLink') }}</RouterLink></p>
      <ConfirmDialog v-if="warnOpen" tone="primary" :title="t('plat.modules.pendingTitle')" :verb="t('plat.modules.pendingVerb')" @cancel="warnOpen = false" @confirm="confirmOff">
        <p class="bs-mute" style="margin: 0 0 8px">{{ t('plat.modules.pendingLede') }}</p>
        <ul style="margin: 0; padding-left: 18px; display: grid; gap: 6px"><li v-for="w in warnings" :key="w">{{ w }}</li></ul>
      </ConfirmDialog>
      <div><AppButton icon="check" variant="secondary" :loading="busy" :disabled="!changed" @click="save">{{ t('plat.modules.save') }}</AppButton></div>
    </template>
  </template>
</template>
