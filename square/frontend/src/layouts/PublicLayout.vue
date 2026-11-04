<script setup lang="ts">
import SiteHeader from '../components/layout/SiteHeader.vue'
import SiteFooter from '../components/layout/SiteFooter.vue'
import { useAdminPreview } from '../composables/useAdminPreview'
import LayoutShell from '../layout-themes/LayoutShell.vue'
import { activeLayout } from '../layout-themes/layouts'

// A square on a layout theme (W9-R5) gets that theme's header, navigation and footer; the default theme keeps the original ones below.
const { adminPreviewActive } = useAdminPreview()
const themed = activeLayout !== null
</script>

<template>
  <LayoutShell v-if="themed" />
  <div v-else class="ds-scope flex min-h-full flex-col">
    <SiteHeader />

    <div v-if="adminPreviewActive" class="admin-preview-banner ds-alert ds-alert-info" role="status" style="border-radius: 0; justify-content: center; text-align: center">
      <div><strong>Admin preview</strong> — this page isn't published yet. Only signed-in admins can see it.</div>
    </div>

    <main class="flex-1">
      <router-view />
    </main>

    <SiteFooter />
  </div>
</template>
