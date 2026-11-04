<script setup lang="ts">
import { useI18n } from 'vue-i18n'

// The dark brand panel on the right of the sign-in screens (Brass screen 13): the logo mark, the name and one line. Same markup as LoginView and SignupView.
const { t } = useI18n()
</script>

<template>
  <aside class="si-side" aria-hidden="true">
    <div class="si-brand">
      <svg class="si-art" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" stroke-width="2.2" /><path d="M12 4v9M12 9l-4 3M12 9l4 3" stroke="var(--color-brass)" stroke-width="2.2" stroke-linecap="round" /></svg>
      <span class="si-name">rootsquares</span>
      <span class="si-sub">{{ t('plat.login.brandSub') }} <em>{{ t('plat.login.brandSubEm') }}</em></span>
    </div>
    <p class="si-q">{{ t('plat.login.sideLead') }} <em>{{ t('plat.login.sideEm') }}</em></p>
  </aside>
</template>
