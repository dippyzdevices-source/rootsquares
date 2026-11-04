<script setup lang="ts">
import { SETTINGS_GROUPS, useSettingsGroup } from '../composables/useSettingsGroup'

// Underlined tab strip for the admin Settings area: the high-level groups (Site, People,
// Pages & media, Lists). A tab opens that group's cards on the hub and stays active on every sub-page that
// belongs to the group.
const active = useSettingsGroup()
</script>

<template>
  <nav class="ds-scope ds-tabs section-tabs settings-section-nav" aria-label="Settings sections" style="flex-wrap: wrap; row-gap: 0">
    <router-link
      v-for="group in SETTINGS_GROUPS"
      :key="group.key"
      :to="group.to ?? { path: '/admin/content', query: { group: group.key } }"
      class="ds-tab"
      :class="{ 'ds-tab-active': active === group.key }"
      style="text-decoration: none; display: inline-block"
      active-class=""
      exact-active-class=""
      :aria-current="active === group.key ? 'page' : undefined"
    >
      {{ group.label }}
    </router-link>
  </nav>
</template>
