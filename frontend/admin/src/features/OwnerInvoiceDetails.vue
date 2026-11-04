<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { errorText } from '@/errorText'
import { type InvoiceSeller } from '@rootsquares/ui/types/platformTypes'
import { adminApi as platform } from '@/adminApi'

// Owner console, Prices page (W19-R16): who the seller is on the invoices owners print from their Payments page. Platform settings kept as data; an empty field is not shown on the invoice.
const { t } = useI18n()
const { push } = useToast()
const form = reactive<InvoiceSeller>({ name: '', org_no: '', address: '', email: '', prefix: 'RS', footer: '' })
const busy = ref(false)
const error = ref('')
const FIELDS = ['name', 'org_no', 'address', 'email', 'prefix', 'footer'] as const
const LABEL: Record<(typeof FIELDS)[number], string> = { name: 'own.invoice.name', org_no: 'own.invoice.orgNo', address: 'own.invoice.address', email: 'own.invoice.email', prefix: 'own.invoice.prefix', footer: 'own.invoice.footer' }

onMounted(async () => {
  try { Object.assign(form, await platform.invoiceSettings()) } catch (e) { error.value = errorText(t, e) }
})
async function save() {
  busy.value = true
  error.value = ''
  try { Object.assign(form, await platform.saveInvoiceSettings({ ...form })); push(t('own.invoice.saved'), 'success') } catch (e) { error.value = errorText(t, e) } finally { busy.value = false }
}
</script>

<template>
  <section class="oc-card" style="margin-top: 14px" data-testid="invoice-details">
    <h3 class="oc-h3">{{ t('own.invoice.title') }}</h3>
    <form class="oi-body" @submit.prevent="save">
      <p class="oc-mut oi-lede">{{ t('own.invoice.lede') }}</p>
      <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
      <div class="oi-grid">
        <label v-for="f in FIELDS" :key="f" class="oi-f"><span>{{ t(LABEL[f]) }}</span><input v-model="form[f]" class="rs-input" :maxlength="f === 'prefix' ? 10 : 200" :autocomplete="'off'"></label>
      </div>
      <div><button type="submit" class="oc-btn" :disabled="busy"><AppIcon name="check" :size="14" />{{ t('own.invoice.save') }}</button></div>
    </form>
  </section>
</template>

<style scoped>
.oi-body { display: grid; gap: 12px; padding: 14px 18px; }
.oi-lede { margin: 0; font-size: var(--text-sm); }
.oi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px 16px; }
.oi-f { display: grid; gap: 4px; font-size: var(--text-sm); }
.oi-f span { color: var(--color-text-muted); }
</style>
