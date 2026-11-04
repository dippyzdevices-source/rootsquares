<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'

const { t } = useI18n()
</script>

<template>
  <section class="mk-sec">
    <EmptyState icon="search" :title="t('common.notFound')">
      {{ t('common.notFoundText') }}
      <template #action><AppButton to="/">{{ t('common.backHome') }}</AppButton></template>
    </EmptyState>
  </section>
</template>
