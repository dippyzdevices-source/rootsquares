<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import type { PortalAttention } from '@/services/platformTypes'
import { useAttention } from './useAttention'

// "Needs your attention" (W25-R35): at the top of the dashboards, one design-system Alert per thing that waits for the owner, with its action button to the exact card
// (the Alert with an action of `Brass Components.html`: warning, title, text, a small secondary button). Nothing shows when nothing waits. `squareId` limits it to one
// square (the square's own dashboard); without it every square is listed and the square's name is the title.
const props = defineProps<{ squareId?: string }>()
const { t } = useI18n()
const { items } = useAttention()
const shown = computed(() => items.value.filter((a) => !props.squareId || a.square_id === props.squareId))
const link = (a: PortalAttention) => (a.kind === 'support_request' ? `/squares/${a.square_id}/support` : `/squares/${a.square_id}/settings#mail-domain`)
const text = (a: PortalAttention) => t(`attentionStrip.${a.kind}`, { domain: a.detail ?? '', note: a.detail ?? '' })
</script>

<template>
  <div v-if="shown.length" class="at" data-testid="attention-strip" role="group" :aria-label="t('attentionStrip.title')">
    <AppAlert v-for="a in shown" :key="`${a.kind}-${a.square_id}`" tone="warning" :title="squareId ? t('attentionStrip.title') : a.name" :data-testid="`attention-${a.kind}`">
      {{ text(a) }}
      <template #action><AppButton icon="arrow" size="sm" variant="secondary" :to="link(a)">{{ t('attentionStrip.go') }}</AppButton></template>
    </AppAlert>
  </div>
</template>

<style scoped>
.at { display: grid; gap: 8px; margin-bottom: 20px; }
</style>
