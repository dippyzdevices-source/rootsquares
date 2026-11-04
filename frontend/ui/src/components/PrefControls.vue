<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppButton from './AppButton.vue'
import { useUiStore } from '../stores/ui'

// Light/dark switch only: the platform is English only, no language switch (design v4 fixed decisions).
defineProps<{ hideLang?: boolean; hideMode?: boolean }>() // hideLang is kept for old callers: there is no language switch any more
const { t } = useI18n()
const ui = useUiStore()
const label = computed(() => (ui.mode === 'dark' ? t('common.lightMode') : t('common.darkMode')))
</script>

<template>
  <AppButton v-if="!hideMode" variant="ghost" size="sm" icon-only :icon="ui.mode === 'dark' ? 'sun' : 'moon'" :label="label" @click="ui.toggleMode" />
</template>
