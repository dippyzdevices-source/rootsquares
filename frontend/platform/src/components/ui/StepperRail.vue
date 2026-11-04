<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import Wordmark from '@rootsquares/ui/components/Wordmark.vue'

// Wizard stepper rail (.bs-rail / .bs-step) and the mobile progress bar (.bs-prog). done = ink check, current = brass ring, upcoming = hairline circle.
// design/rootsquares-platform-brass/screens/A.jsx Wizard. Used when the wizard is rebuilt (later stage).
const props = defineProps<{ steps: string[]; current: number; mobile?: boolean }>()
const { t } = useI18n()
const state = (i: number) => (i < props.current ? 'done' : i === props.current ? 'cur' : '')
</script>

<template>
  <div v-if="mobile" role="progressbar" :aria-valuenow="current + 1" aria-valuemin="1" :aria-valuemax="steps.length" :aria-label="t('wizard.stepWord')">
    <div class="bs-prog"><i :style="{ width: ((current + 1) / steps.length) * 100 + '%' }" /></div>
  </div>
  <aside v-else class="bs-rail">
    <Wordmark />
    <div>
      <span class="rs-eyebrow">{{ t('wizard.rail') }}</span>
      <ol style="margin: 10px 0 0; padding: 0; list-style: none">
        <li v-for="(s, i) in steps" :key="s" class="bs-step" :class="state(i)" :aria-current="i === current ? 'step' : undefined">
          <i><AppIcon v-if="i < current" name="check" :size="12" /><template v-else>{{ i + 1 }}</template></i>{{ s }}
        </li>
      </ol>
    </div>
    <span class="bs-sp" />
    <slot name="foot" />
  </aside>
</template>
