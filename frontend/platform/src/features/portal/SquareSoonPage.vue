<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import EmptyState from '@/components/ui/EmptyState.vue'
import SquarePlanCard from './SquarePlanCard.vue'
import { useSquare } from './squareContext'

// Billing, Settings and Support access of the portal (design v4 portal nav). Their backend is not built (no billing, no support-access grants, no
// editable square settings: MISSING.md), so each page says so honestly instead of showing invented data. (Settings has its own page, SquareSettingsPage.vue, since W23-R38.)
const { t } = useI18n()
const route = useRoute()
const { sq } = useSquare()
// The router reuses this one component for the three paths, so the kind must follow the route (a plain const kept the first page's words).
const kind = computed(() => String(route.meta.portalPage) as 'billing' | 'settings' | 'support')
const ICON = { billing: 'card', settings: 'sliders', support: 'shield' } as const
</script>

<template>
  <template v-if="sq">
    <div class="bw-hd"><h2 class="bs-h2" style="font-size: 28px">{{ t(`portal.nav.${kind}`) }}</h2><p class="bs-mute" style="margin: 0; font-size: var(--text-sm)">{{ t(`portal.${kind}.lede`) }}</p></div>
    <SquarePlanCard v-if="kind === 'billing'" />
    <EmptyState v-if="kind !== 'billing'" :icon="ICON[kind]" :title="t('portal.soonTitle')">{{ t(`portal.${kind}.soon`) }}</EmptyState>
  </template>
</template>
