<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { errorText } from '@/errorText'
import { adminApi as platform } from '@/adminApi'

// Owner console, Prices page (W19-R27): a guiding minimum per month for each of the five steps of a custom package. Only a platform admin sees or sets it.
// It is advice shown on a square's Package tab, not a rule; 0 or empty = no guide for that step. Amounts are USD like every price.
const { t } = useI18n()
const { push } = useToast()
const STEPS = [0, 1, 2, 3, 4]
const values = ref<string[]>(['', '', '', '', ''])
const busy = ref(false)
const error = ref('')
const show = (minor: number) => (minor ? (minor / 100).toFixed(2).replace(/\.00$/, '') : '')
const minor = (v: string) => { const n = Math.round(parseFloat(v.replace(',', '.')) * 100); return Number.isFinite(n) && n > 0 ? n : 0 }

onMounted(async () => {
  try { values.value = (await platform.customGuide()).map(show) } catch (e) { error.value = errorText(t, e) }
})
async function save() {
  busy.value = true
  error.value = ''
  try { values.value = (await platform.saveCustomGuide(values.value.map(minor))).map(show); push(t('own.guide.saved'), 'success') } catch (e) { error.value = errorText(t, e) } finally { busy.value = false }
}
</script>

<template>
  <section class="oc-card" style="margin-top: 14px" data-testid="custom-guide">
    <h3 class="oc-h3">{{ t('own.guide.title') }}</h3>
    <form class="og-body" @submit.prevent="save">
      <p class="oc-mut og-lede">{{ t('own.guide.lede') }}</p>
      <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
      <div class="og-grid">
        <AppField v-for="s in STEPS" :key="s" v-model="values[s]!" :label="t('own.guide.step', { n: s + 1, name: t(`own.custom.pb.step.${s}.name`) })" :hint="t(`own.custom.pb.step.${s}.text`)" suffix="USD" placeholder="0" />
      </div>
      <div><button type="submit" class="oc-btn" :disabled="busy"><AppIcon name="check" :size="14" />{{ t('own.guide.save') }}</button></div>
    </form>
  </section>
</template>

<style scoped>
.og-body { display: grid; gap: 12px; padding: 14px 18px; }
.og-lede { margin: 0; font-size: var(--text-sm); }
.og-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px 16px; }
</style>
