<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import DataRow from '@rootsquares/ui/components/DataRow.vue'
import { platform, type PlatformSquare } from '@/services/platform'
import { errorText } from '@/features/platform/errorText'
import SquareStatusChip from '@/features/platform/SquareStatusChip.vue'
import { provideSquare } from './squareContext'

// Route component of /squares/:id: loads the square (polls every 2 s while it is being set up), shows the crumb (Your squares / the square's name) on the left and
// the status chip (on every page, the Your square page included, W24-R15) and the Back to squares button on the right (W24-R14, from the design Support Access Redesign),
// and the loading and error states of design v4 (screens/I.jsx Console: skeleton rows, danger alert with Try again). The pages are its children.
const { t } = useI18n()
const route = useRoute()
const sq = ref<PlatformSquare | null>(null)
const error = ref('')
const notFound = ref(false)
const loading = ref(true)
let timer: ReturnType<typeof setInterval> | undefined
const id = computed(() => String(route.params.id))

async function load() {
  try {
    sq.value = await platform.getSquare(id.value)
    error.value = ''
    notFound.value = false
  } catch (e) {
    if (timer) { clearInterval(timer); timer = undefined }
    notFound.value = (e as { status?: number }).status === 404
    error.value = errorText(t, e)
    loading.value = false
    return
  }
  loading.value = false
  const busy = sq.value.status === 'provisioning'
  if (busy && !timer) timer = setInterval(load, 2000)
  if (!busy && timer) { clearInterval(timer); timer = undefined }
}
provideSquare({ sq, set: (v) => { sq.value = v; if (v.status === 'provisioning' && !timer) timer = setInterval(load, 2000) }, reload: load })
onMounted(load)
watch(id, () => { sq.value = null; loading.value = true; void load() })
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div style="display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; align-content: start">
    <div class="sf-top">
      <nav :aria-label="t('plat.detail.crumb')">
        <ol class="rs-crumbs">
          <li><RouterLink class="sf-link" to="/dashboard">{{ t('plat.detail.back') }}</RouterLink><span aria-hidden="true">/</span></li>
          <li v-if="sq" class="sf-name" aria-current="page">{{ sq.name }}</li>
        </ol>
      </nav>
      <div class="sf-right">
        <SquareStatusChip v-if="sq" :status="sq.status" :awaiting-payment="sq.awaiting_payment" />
        <AppButton icon="chevron-left" class="sf-back" to="/dashboard" variant="secondary" size="sm">{{ t('plat.detail.backBtn') }}</AppButton>
      </div>
    </div>
    <template v-if="sq">
      <h1 v-if="route.name !== 'square'" class="rs-sr">{{ sq.name }}</h1>
      <RouterView />
    </template>
    <div v-else-if="loading" class="bx-list" aria-busy="true"><span class="bx-sk" style="height: 36px; width: 200px" /><DataRow v-for="i in 3" :key="i" loading /></div>
    <AppAlert v-else tone="danger" :title="notFound ? t('plat.detail.notFound') : t('bx.errorTitle')">
      {{ error }}
      <template v-if="!notFound" #action><button type="button" class="rs-btn rs-btn--secondary rs-btn--sm" @click="load"><AppIcon name="refresh" :size="14" />{{ t('bx.retry') }}</button></template>
    </AppAlert>
  </div>
</template>

<style scoped>
/* The crumb at the left; the status chip and the back button at the right. The back button keeps the style of the buttons of the square page (W23-R28): a pill, capitals, a light outline (the theme's secondary button has a dark one). */
.sf-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.sf-right { display: flex; align-items: center; gap: 10px; }
.sf-link { color: var(--color-brass-text); text-underline-offset: 3px; }
.sf-link:hover { color: var(--color-text); }
.sf-name { overflow-wrap: anywhere; }
.sf-back.sf-back { padding: 0 14px; border-radius: var(--shape-control); border-color: var(--color-border); background: var(--color-surface); color: var(--color-text); font: 600 11px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; white-space: nowrap; }
.sf-back.sf-back:hover { border-color: var(--color-border); background: var(--color-surface-sunken); }
</style>
