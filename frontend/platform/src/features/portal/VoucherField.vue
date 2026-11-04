<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import { errorText } from '@/features/platform/errorText'
import { usd } from '@rootsquares/ui/mock/pricing'
import { platform, type CheckoutInput, type VoucherCheck } from '@/services/platform'

// "Have a voucher?" (W14-R27): a code box next to a payment. The code travels with the checkout; with `preview` (and a square) the box also shows what it would take off
// before the customer pays. A code lowers a launch package or an Event pass once, so it is not offered for a monthly or yearly plan on its own.
const props = defineProps<{ modelValue: string; squareId?: string; preview?: CheckoutInput; check?: (code: string) => Promise<VoucherCheck>; error?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const { t } = useI18n()
const result = ref<VoucherCheck | null>(null)
const problem = ref('')
const busy = ref(false)

watch(() => [props.modelValue, props.preview], () => { result.value = null; problem.value = '' }, { deep: true })

async function run() {
  const code = props.modelValue.trim()
  if (!code || !(props.check || (props.squareId && props.preview))) return
  busy.value = true
  problem.value = ''
  try { result.value = props.check ? await props.check(code) : await platform.voucherCheck(props.squareId!, { ...props.preview!, code }) } catch (e) { problem.value = errorText(t, e) } finally { busy.value = false }
}
</script>

<template>
  <div class="vf" data-testid="voucher-field">
    <label class="vf__label" :for="`vf-${squareId ?? 'new'}`">{{ t('portal.voucher.title') }}</label>
    <div class="vf__row">
      <input :id="`vf-${squareId ?? 'new'}`" class="vf__in" :value="modelValue" :placeholder="t('portal.voucher.placeholder')" autocomplete="off" autocapitalize="characters" @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)" @keyup.enter="run">
      <AppButton v-if="check || (squareId && preview)" icon="check" variant="secondary" :disabled="busy || !modelValue.trim()" @click="run">{{ t('portal.voucher.apply') }}</AppButton>
    </div>
    <small v-if="!result && !problem && !error" class="bs-mute">{{ t('portal.voucher.hint') }}</small>
    <small v-if="error || problem" class="vf__bad" role="alert">{{ error || problem }}</small>
    <small v-else-if="result && !result.valid" class="vf__bad" role="alert">{{ t(`plat.errors.${result.reason}`) === `plat.errors.${result.reason}` ? result.message : t(`plat.errors.${result.reason}`) }}</small>
    <small v-else-if="result" class="vf__ok" role="status">
      <template v-if="result.codes && result.codes.length > 1">{{ result.codes.join(' + ') }} · </template>
      {{ t('portal.voucher.off', { amount: usd(result.discount_minor) }) }} ·
      {{ t('portal.voucher.nowTotal', { amount: usd(result.payable_minor), before: usd(result.list_minor) }) }}
    </small>
    <small v-if="result && result.valid && result.ignored && result.ignored.length" class="vf__note" role="status" data-testid="voucher-ignored">
      {{ result.ignored.map((i) => `${i.code}: ${i.why}`).join(' · ') }}
    </small>
  </div>
</template>

<style scoped>
.vf { display: grid; gap: 6px; max-width: 360px }
@media (max-width: 640px) { .vf { max-width: none } } /* full width on a phone (W25-R52) */
.vf__label { font-weight: 500; font-size: var(--text-sm) }
.vf__row { display: flex; gap: 8px }
.vf__in { flex: 1; min-width: 0; min-height: 44px; padding: 0 12px; border: 1px solid var(--color-border); border-radius: var(--shape-field); background: var(--color-surface); color: var(--color-text); font: inherit; text-transform: uppercase }
.vf__in:focus-visible { outline: 2px solid var(--color-brass); outline-offset: 1px }
.vf__bad, .vf__ok { padding: 8px 10px; border-radius: var(--shape-surface); border: 1px solid; font-size: var(--text-sm); font-weight: 500; line-height: 1.4 }
.vf__note { color: var(--color-text-muted, var(--color-text)); font-size: var(--text-sm) }
.vf__bad { color: var(--color-danger); background: var(--color-danger-subtle); border-color: var(--color-danger) }
.vf__ok { color: var(--color-success); background: var(--color-success-subtle); border-color: var(--color-success) }
</style>
