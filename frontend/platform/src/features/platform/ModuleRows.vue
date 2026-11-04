<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { useI18n } from 'vue-i18n'
import SwitchBtn from '@/components/ui/SwitchBtn.vue'
import type { ModuleInfo, ModuleStatus } from '@/services/platform'

// The rows of the modules picker (W15-R27): name, one line, and a switch. A module the launch package does not include has an Upgrade button instead of a switch
// (a link to Billing when `upgradeTo` is given, else a plain tag); `readonly` rows show that the package includes the module, with no switch.
// A sub-switch is indented only when its parent is in the same list (W14-R13) and is greyed while the parent is off.
const props = defineProps<{ items: ModuleInfo[]; modules: ModuleInfo[]; modelValue: string[]; disabled?: boolean; status?: ModuleStatus[]; allowed?: string[]; upgradeTo?: string; readonly?: boolean }>()
const emit = defineEmits<{ toggle: [key: string, on: boolean] }>()
const { t } = useI18n()

const outside = (m: ModuleInfo) => !!props.allowed && !props.allowed.includes(m.key)
const locked = (m: ModuleInfo) => !props.readonly && outside(m)
const isChild = (m: ModuleInfo) => !!m.parent && props.items.some((p) => p.key === m.parent)
const parentOff = (m: ModuleInfo) => !!m.parent && !props.modelValue.includes(m.parent)
// An OFF module that holds data says so, in words and without a number (W8-R27, ADR 038); one that never held data says nothing.
function storedText(m: ModuleInfo): string {
  if (props.readonly || props.modelValue.includes(m.key)) return ''
  return props.status?.find((s) => s.key === m.key)?.holds_data ? ` ${t('plat.modules.stored')}` : ''
}
function needsText(m: ModuleInfo): string {
  const names = m.needs.map((k) => props.modules.find((x) => x.key === k)?.label ?? k)
  // some descriptions already say what they need: do not say it twice
  return names.length && !m.description.includes('Needs') ? ` ${t('plat.modules.needs', { names: names.join(', ') })}` : ''
}
</script>

<template>
  <div v-for="m in items" :key="m.key" class="bw-mod" :data-module="m.key" :data-locked="locked(m) || undefined" :data-child="isChild(m) || undefined" :style="isChild(m) ? 'margin-left: 22px; border-left: 2px solid var(--line, #ddd6c6); padding-left: 12px' : undefined">
    <b>{{ m.label }}</b>
    <small>{{ m.description + needsText(m) + storedText(m) }}<template v-if="locked(m)"> {{ t('plat.modules.locked') }}</template></small>
    <span class="sw">
      <span v-if="readonly && !outside(m)" class="rs-chip rs-chip--info">{{ t('plat.modules.views.included') }}</span>
      <template v-else-if="outside(m)">
        <RouterLink v-if="upgradeTo" :to="upgradeTo" class="rs-btn rs-btn--secondary rs-btn--sm" data-testid="upgrade"><AppIcon name="card" :size="14" />{{ t('plat.modules.views.upgrade') }}</RouterLink>
        <span v-else class="rs-chip rs-chip--draft">{{ t('plat.modules.views.upgrade') }}</span>
      </template>
      <SwitchBtn v-else :model-value="modelValue.includes(m.key)" :label="m.label" :disabled="disabled || parentOff(m)" @update:model-value="emit('toggle', m.key, $event)" />
    </span>
  </div>
</template>
