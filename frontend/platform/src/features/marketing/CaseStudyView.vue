<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import { getCaseStats } from '@/services/marketing'
import { CASE_STRIP } from '@/mock/placeholders'

// BCA case study, design v4 (screens/I.jsx Case, ext2.css .bp-*): eyebrow, serif H1 with one brass italic phrase, screenshot placeholder, a strip of
// three figures, then a meta list beside the article (serif H2 28px, italic serif pull quote). Every word and figure is a placeholder.
const { t } = useI18n()
const loading = ref(true)
const failed = ref(false)
async function load() {
  loading.value = true
  failed.value = false
  try { await getCaseStats() } catch { failed.value = true }
  loading.value = false
}
onMounted(load)
const figures = ['tickets', 'members', 'guests'] as const
const meta = ['client', 'size', 'modules', 'since'] as const
</script>

<template>
  <section class="bp-hero" style="justify-items: start; text-align: start">
    <span class="rs-eyebrow">{{ t('marketing.case.eyebrow') }}</span>
    <h1 style="max-width: 18ch">{{ t('marketing.case.title') }} <em>{{ t('marketing.case.titleEm') }}</em></h1>
    <p class="bs-mute" style="margin: 0; max-width: 52ch">{{ t('marketing.case.lede') }}</p>
  </section>
  <div v-if="failed" style="padding: 0 var(--page-x)">
    <AppAlert tone="danger" :title="t('marketing.case.errorTitle')">
      {{ t('marketing.case.errorText') }}
      <template #action><AppButton variant="secondary" size="sm" @click="load">{{ t('marketing.case.retry') }}</AppButton></template>
    </AppAlert>
  </div>
  <template v-else>
    <div class="bs-shot" style="margin: 0 var(--page-x); min-height: 260px; padding: 0; overflow: hidden">
      <img src="/case-bca.jpg" :alt="t('marketing.case.shot')" style="width: 100%; height: auto; display: block" />
    </div>
    <div class="bp-fig" style="margin-top: 20px" :aria-busy="loading || undefined">
      <div v-for="(f, i) in figures" :key="f">
        <template v-if="loading"><span class="bx-sk" style="height: 34px; width: 90px" /><span class="bx-sk" style="height: 12px; width: 150px" /></template>
        <template v-else><b>{{ CASE_STRIP[i] }}</b><span>{{ t(`marketing.case.stats.${f}`) }}</span></template>
      </div>
    </div>
    <div class="bp-art">
      <dl style="display: grid; gap: 8px; align-content: start; margin: 0">
        <div v-for="m in meta" :key="m" style="display: grid; grid-template-columns: 80px 1fr; font-size: var(--text-sm); border-top: 1px solid var(--color-border); padding-top: 8px">
          <dt class="bs-mute">{{ t(`marketing.case.meta.${m}`) }}</dt><dd style="margin: 0">{{ t(`marketing.case.meta.${m}Value`) }}</dd>
        </div>
      </dl>
      <div>
        <h2 class="bs-h2" style="margin-bottom: 12px; font-size: 28px">{{ t('marketing.case.challenge') }}</h2>
        <p>{{ t('marketing.case.challengeText') }}</p>
        <blockquote class="bp-q">“{{ t('marketing.case.quote') }}”</blockquote>
        <p class="bs-mute" style="font-size: var(--text-sm)">{{ t('marketing.case.quoteBy') }}</p>
        <h2 class="bs-h2" style="margin: 16px 0 12px; font-size: 28px">{{ t('marketing.case.result') }}</h2>
        <p>{{ t('marketing.case.resultText') }}</p>
        <blockquote class="bp-q">“{{ t('marketing.case.quote2') }}”</blockquote>
        <p class="bs-mute" style="font-size: var(--text-sm)">{{ t('marketing.case.quote2By') }}</p>
        <AppButton size="lg" icon="arrow" to="/signup">{{ t('marketing.case.cta') }}</AppButton>
      </div>
    </div>
  </template>
</template>
