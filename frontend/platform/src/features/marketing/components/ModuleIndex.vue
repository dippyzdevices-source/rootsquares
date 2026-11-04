<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import ModulePreview from './ModulePreview.vue'
import { MODULE_IDS, type ModuleId } from '@/mock/landing'

// Module index: seven hairline rows (number, name, descriptor). Wide: the preview panel on the right follows hover, focus or tap.
// Narrow: each row expands in place. The row pattern is Brass .bs-li; the panel and the expanding behaviour are not in the design.
const { t } = useI18n()
const active = ref<ModuleId>('events')
const openRow = ref<ModuleId | null>('events')
const pad = (i: number) => String(i + 1).padStart(2, '0')
function toggle(id: ModuleId) {
  active.value = id
  openRow.value = openRow.value === id ? null : id
}
</script>

<template>
  <div class="bs-mods">
    <ul class="bs-mods__list" role="list">
      <li v-for="(id, i) in MODULE_IDS" :key="id">
        <button
          type="button"
          class="bs-li bs-li--btn"
          :class="active === id && 'is-active'"
          :aria-expanded="openRow === id"
          :aria-controls="`mod-${id}`"
          @mouseenter="active = id"
          @focus="active = id"
          @click="toggle(id)"
        >
          <span class="bs-n">{{ pad(i) }}</span>
          <b>{{ t(`landing.modules.${id}.name`) }}</b>
          <span class="bs-li__hint">{{ t(`landing.modules.${id}.hint`) }}</span>
          <AppIcon class="bs-li__chev" :name="openRow === id ? 'chevron-up' : 'chevron-down'" :size="14" />
        </button>
        <div v-if="openRow === id" :id="`mod-${id}`" class="bs-mods__inline"><ModulePreview :id="id" /></div>
      </li>
    </ul>
    <div class="bs-mods__panel" aria-live="polite"><ModulePreview :id="active" /></div>
  </div>
</template>
