<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import CopyField from '@/components/ui/CopyField.vue'
import SquareSiteDomainCard from './SquareSiteDomainCard.vue'
import { useSquare } from './squareContext'

// W13-R40: the two parts are console cards (oc-card); the 28px heading stays.
// Domain page: the square's address (read only; every square has one) and the own website domain (W26-R5, ADR 098, Grove: a CNAME at squares.rootsquares.com).
const { t } = useI18n()
const { sq } = useSquare()
</script>

<template>
  <template v-if="sq">
    <div class="bw-hd"><h2 class="bs-h2" style="font-size: 28px">{{ t('portal.nav.domain') }}</h2><p class="bs-mute" style="margin: 0; font-size: var(--text-sm)">{{ t('portal.domain.lede') }}</p></div>
    <section class="oc-card">
      <h3 class="oc-h3">{{ t('portal.domain.subdomain') }}</h3>
      <div class="oc-li"><span class="oc-mut">{{ t('plat.detail.domain') }}</span><span style="word-break: break-all">{{ sq.domain }}</span></div>
      <div style="padding: 14px 18px"><CopyField :value="sq.url" :label="t('bx.copy')" /></div>
    </section>
    <SquareSiteDomainCard :square-id="sq.id" />
  </template>
</template>
