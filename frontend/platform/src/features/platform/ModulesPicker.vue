<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppTabs from '@rootsquares/ui/components/AppTabs.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import ModuleRows from './ModuleRows.vue'
import { arrangeModules, modulesOfPackage, packageAdditions, recommendationGroups, recommendedModules, withModule, withoutModule } from '@/services/modulesCatalogue'
import type { LaunchPackageId, ModuleInfo, ModuleStatus } from '@/services/platform'

// The owner's choice of modules (docs/reference/optional-modules.md, docs/plans/module-views-plan.md), in three views (W15-R27):
//   All modules      one list of every module; those the launch package does not include have an Upgrade button;
//   By package       what Root, Square, Grove and the Event pass each include (read-only; the square's own package is marked);
//   Recommended      Basic (the always-on parts), Recommended (the list of the square's kind of group) and Good to have (everything else).
// Switching one on switches on what it needs; switching one off switches off what needs it (Memberships needs Members; Members works alone, ADR 044).
const props = defineProps<{
  modules: ModuleInfo[]
  modelValue: string[]
  disabled?: boolean
  status?: ModuleStatus[]
  allowed?: string[]
  launchPackage?: string | null // the square's package, marked in 'By package'
  recommended?: string[] // the kind of group's list; without it the modules' own tiers decide
  kindLabel?: string // 'Cultural group', for the one-line advice
  upgradeTo?: string // where the Upgrade button goes (Billing); without it the button is a plain tag
}>()
const emit = defineEmits<{ 'update:modelValue': [v: string[]] }>()
const { t } = useI18n()
const CORE = ['home', 'about', 'contact', 'login', 'legal', 'settings', 'media', 'admin', 'account']
const PACKAGES: LaunchPackageId[] = ['roots', 'square', 'grove', 'event']

const view = ref<'all' | 'package' | 'recommended'>('recommended')
const viewItems = computed<[string, string][]>(() => [
  ['all', t('plat.modules.views.all')],
  ['package', t('plat.modules.views.package')],
  ['recommended', t('plat.modules.views.recommended')],
])
// the counts are about what the launch package lets the owner use: a module the package does not include is not counted, even if it is still on from before (W15-R33)
const usable = (items: ModuleInfo[]) => (props.allowed ? items.filter((m) => props.allowed!.includes(m.key)) : items)
const onCount = (items: ModuleInfo[]) => usable(items).filter((m) => props.modelValue.includes(m.key)).length
const totalCount = (items: ModuleInfo[]) => usable(items).length
const lockedCount = (items: ModuleInfo[]) => items.length - totalCount(items)
const lockedNote = (items: ModuleInfo[]) => (lockedCount(items) ? ` · ${t('plat.modules.views.needUpgrade', { n: lockedCount(items) })}` : '')

// 1. all modules
const all = computed(() => arrangeModules(props.modules, props.modules.map((m) => m.key)))

// 2. by package
const pkg = ref<string>(PACKAGES.includes(props.launchPackage as LaunchPackageId) ? (props.launchPackage as string) : 'square')
const pkgName = (p: string) => t(p === 'event' ? 'marketing.pricing.running.event.name' : `marketing.pricing.launch.${p}.name`)
// Each package shows only what it ADDS to the one before (W15-R30): Root = the always-on parts, Square = Root + its modules, Grove = Square + its extras.
// The Event pass is its own list, not a step of that ladder.
const adds = (p: LaunchPackageId): ModuleInfo[] => packageAdditions(props.modules, p)
const pkgTabs = computed(() =>
  PACKAGES.map((p) => ({
    id: p,
    label: pkgName(p),
    mark: p === props.launchPackage ? t('plat.modules.views.yours') : undefined,
    count: p === 'roots' ? CORE.length : p === 'event' ? adds(p).length : `+${adds(p).length}`,
  })),
)
const pkgItems = computed(() => adds(pkg.value as LaunchPackageId))
const pkgNote = computed(() => (pkg.value === 'square' ? t('plat.modules.views.plusRoot') : pkg.value === 'grove' ? t('plat.modules.views.plusSquare') : pkg.value === 'event' ? t('plat.modules.views.eventOwn') : t('plat.modules.views.rootIs')))
// how many of the square's own package are on, out of how many (W15-R28)
const mineAll = computed(() => (PACKAGES.includes(props.launchPackage as LaunchPackageId) ? modulesOfPackage(props.modules, props.launchPackage as LaunchPackageId) : []))

// 3. by recommendation
const groups = computed(() => recommendationGroups(props.modules, props.recommended ?? recommendedModules(props.modules)))
const group = ref<'always' | 'recommended' | 'good_to_have'>('recommended')
const groupTabs = computed(() => [
  { id: 'always', label: t('plat.modules.alwaysOn'), count: CORE.length },
  { id: 'recommended', label: t('plat.modules.recommended'), count: `${onCount(groups.value.recommended)}/${totalCount(groups.value.recommended)}` },
  { id: 'good_to_have', label: t('plat.modules.goodToHave'), count: `${onCount(groups.value.goodToHave)}/${totalCount(groups.value.goodToHave)}` },
])
const groupItems = computed(() => (group.value === 'recommended' ? groups.value.recommended : groups.value.goodToHave))
const groupLede = computed(() => {
  if (group.value === 'always') return t('plat.modules.alwaysOnLede')
  if (group.value === 'good_to_have') return t('plat.modules.views.goodToHaveLede')
  return props.kindLabel ? t('plat.modules.views.recommendedLede', { kind: props.kindLabel.toLowerCase() }) : t('plat.modules.views.recommendedLedeNoKind')
})

function toggle(key: string, on: boolean) {
  emit('update:modelValue', on ? withModule(props.modules, props.modelValue, key, props.allowed) : withoutModule(props.modules, props.modelValue, key))
}
</script>

<template>
  <div style="display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px" data-testid="modules-picker">
    <div class="mp-views"><SegmentedControl v-model="view" :items="viewItems" :label="t('plat.modules.views.label')" /></div>

    <div v-if="view === 'all'" style="display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px" data-view="all">
      <p class="bs-mute" style="margin: 0; font-size: var(--text-sm)">{{ t('plat.modules.views.allLede') }} <b style="font-weight: 500; color: var(--color-text)" data-testid="count-all">{{ t('plat.modules.views.allCount', { on: onCount(all), total: totalCount(all) }) + lockedNote(all) }}</b></p>
      <div class="bw-sum" role="group" :aria-label="t('plat.modules.views.all')" style="padding: 0 14px">
        <ModuleRows :items="all" :modules="modules" :model-value="modelValue" :disabled="disabled" :status="status" :allowed="allowed" :upgrade-to="upgradeTo" @toggle="toggle" />
      </div>
    </div>

    <div v-else-if="view === 'package'" style="display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px" data-view="package">
      <p class="bs-mute" style="margin: 0; font-size: var(--text-sm)">{{ t('plat.modules.views.packageLede') }}</p>
      <p v-if="mineAll.length" class="mp-yours" data-testid="count-package"><b>{{ t('plat.modules.views.yourCount', { package: pkgName(launchPackage as string), on: onCount(mineAll), total: mineAll.length }) }}</b></p>
      <AppTabs v-model="pkg" :tabs="pkgTabs" :label="t('plat.modules.views.package')" />
      <p class="bs-mute" style="margin: 0; font-size: var(--text-sm)" data-testid="package-note">{{ pkgNote }}</p>
      <div class="bw-sum" role="group" :aria-label="pkgName(pkg)" style="padding: 0 14px">
        <template v-if="pkg === 'roots'">
          <div v-for="k in CORE" :key="k" class="bw-mod" :data-core="k">
            <b>{{ t(`plat.modules.coreItems.${k}.name`) }}</b>
            <small>{{ t(`plat.modules.coreItems.${k}.text`) }}</small>
            <span class="sw"><span class="rs-chip rs-chip--info">{{ t('plat.modules.alwaysOnChip') }}</span></span>
          </div>
        </template>
        <ModuleRows v-else :items="pkgItems" :modules="modules" :model-value="modelValue" :status="status" :allowed="allowed" :upgrade-to="upgradeTo" readonly />
      </div>
    </div>

    <div v-else style="display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px" data-view="recommended">
      <AppTabs v-model="group" :tabs="groupTabs" :label="t('plat.modules.views.recommended')" />
      <p class="bs-mute" style="margin: 0; font-size: var(--text-sm)">{{ groupLede }}
        <b v-if="group !== 'always'" style="font-weight: 500; color: var(--color-text)" data-testid="count-group">{{ t('plat.modules.views.groupCount', { on: onCount(groupItems), total: totalCount(groupItems) }) + lockedNote(groupItems) }}</b>
      </p>
      <div class="bw-sum" role="group" :aria-label="groupTabs.find((x) => x.id === group)?.label" style="padding: 0 14px">
        <template v-if="group === 'always'">
          <div v-for="k in CORE" :key="k" class="bw-mod" :data-core="k">
            <b>{{ t(`plat.modules.coreItems.${k}.name`) }}</b>
            <small>{{ t(`plat.modules.coreItems.${k}.text`) }}</small>
            <span class="sw"><span class="rs-chip rs-chip--info">{{ t('plat.modules.alwaysOnChip') }}</span></span>
          </div>
        </template>
        <ModuleRows v-else :items="groupItems" :modules="modules" :model-value="modelValue" :disabled="disabled" :status="status" :allowed="allowed" :upgrade-to="upgradeTo" @toggle="toggle" />
      </div>
    </div>

    <span class="bs-mute" style="font-size: var(--text-xs)" aria-live="polite">{{ t('plat.modules.count', { n: onCount(modules), total: totalCount(modules) }) }}</span>
  </div>
</template>

<style scoped>
/* The view switcher is a brass pill, apart from the quiet underline tabs below it (W15-R28). Brass is mixed with the text colour so the label stays readable in light and dark. */
.mp-views :deep(.rs-seg) { display: flex; width: 100%; padding: 3px; gap: 3px; border: 1px solid var(--color-border-strong); border-radius: var(--shape-control); background: var(--color-surface-sunken, var(--color-surface)) }
.mp-views :deep(.rs-seg button) { flex: 1; min-height: 32px; padding: 0 16px; border-radius: var(--shape-control); font-size: var(--text-sm); font-weight: 600; letter-spacing: .01em; transition: background .15s ease, color .15s ease, box-shadow .15s ease }
.mp-views :deep(.rs-seg button[aria-pressed='true']) { background: color-mix(in srgb, var(--color-brass) 78%, var(--color-text)); color: var(--color-bg); box-shadow: 0 1px 2px rgba(0, 0, 0, .25) }
.mp-views :deep(.rs-seg button:focus-visible) { outline: 2px solid var(--color-brass); outline-offset: 2px }
/* On a phone the three views fit the width: smaller sides and text, and the buttons may shrink (W25-R53) */
@media (max-width: 640px) { .mp-views { min-width: 0; } .mp-views :deep(.rs-seg button) { min-width: 0; padding: 0 6px; font-size: var(--text-xs); white-space: nowrap; } }
@media (max-width: 640px) { [data-testid='modules-picker'] :deep(.rs-tab) { flex: 1 1 0; min-width: 0; justify-content: center; padding: 0 6px; gap: 4px; min-height: 40px; font-size: var(--text-xs); white-space: nowrap; } } /* the sub tabs share the width instead of scrolling sideways (W25-R53) */
.mp-yours { margin: 0; padding: 8px 12px; border-left: 3px solid var(--color-brass); border-radius: 0 6px 6px 0; background: var(--color-brass-subtle); color: var(--color-brass-text); font-size: var(--text-sm) }
.mp-yours b { font-weight: 600 }
</style>
