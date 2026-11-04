<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import { platform, type PlatformSquare } from '@/services/platform'
import { errorText } from '@/features/platform/errorText'
import { provideSquare } from './squareContext'

// Route component of /squares/:id/theme/studio (W19-R3): loads the square and gives it to the studio like SquareFrame does, but draws nothing around it (no header, no side bar),
// so the studio has the whole window. No polling: a square that is still being set up is sent back to the Theme page, which shows the state.
const { t } = useI18n()
const route = useRoute()
const sq = ref<PlatformSquare | null>(null)
const error = ref('')
const notFound = ref(false)
const id = computed(() => String(route.params.id))

async function load() {
  try { sq.value = await platform.getSquare(id.value); error.value = ''; notFound.value = false } catch (e) { notFound.value = (e as { status?: number }).status === 404; error.value = errorText(t, e) }
}
provideSquare({ sq, set: (v) => { sq.value = v }, reload: load })
onMounted(load)
watch(id, () => { sq.value = null; void load() })
</script>

<template>
  <RouterView v-if="sq" />
  <div v-else class="tsf">
    <AppAlert v-if="error" tone="danger" :title="notFound ? t('plat.detail.notFound') : t('bx.errorTitle')">
      {{ error }}
      <template #action><RouterLink :to="`/squares/${id}/theme`" class="rs-btn rs-btn--secondary rs-btn--sm"><AppIcon name="chevron-left" :size="14" />{{ t('portal.theme.studio.back') }}</RouterLink></template>
    </AppAlert>
    <div v-else class="tsf-wait" role="status"><span class="tsf-spin" aria-hidden="true" /><b>{{ t('portal.theme.studio.opening') }}</b></div>
  </div>
</template>

<style scoped>
.tsf { display: grid; place-items: center; min-height: 100dvh; padding: 24px; }
.tsf-wait { display: grid; justify-items: center; gap: 14px; color: var(--color-text); font-size: var(--text-sm); }
.tsf-spin { width: 36px; height: 36px; border-radius: 50%; border: 3px solid var(--color-border); border-top-color: var(--color-brass); animation: tsf-turn 0.9s linear infinite; }
@keyframes tsf-turn { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .tsf-spin { animation: none; } }
</style>
