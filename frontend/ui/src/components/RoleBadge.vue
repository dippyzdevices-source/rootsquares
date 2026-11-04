<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AppIcon from './AppIcon.vue'

// Design v3 Role badge (`.bx-role--owner|admin|editor|viewer|support`): icon + label, hairline; owner = brass, support = dashed.
defineProps<{ role: 'owner' | 'admin' | 'editor' | 'viewer' | 'support' }>()
const { t } = useI18n()
const ICON = { owner: 'key', admin: 'shield', editor: 'edit', viewer: 'eye', support: 'shield' } as const
</script>

<template>
  <span class="bx-role" :class="`bx-role--${role}`"><AppIcon :name="ICON[role]" :size="12" />{{ t(`bx.roles.${role}`) }}</span>
</template>
