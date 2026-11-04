<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import LaunchPreview from './components/LaunchPreview.vue'
import ModuleIndex from './components/ModuleIndex.vue'
import { BCA_STATS } from '@/mock/landing'
import { LAUNCH_PACKAGES, usd } from '@rootsquares/ui/mock/pricing'
import { loadPrices, minorOf } from '@/services/prices'
import { CASE_FIGURES } from '@/mock/placeholders'

// Landing page (/), rebuilt from "Landing Redesign.html" in the rootsquares design project (W11-R47): hero (unchanged), what you get with the domain card,
// who it is for (a light band), the BCA Oslo proof, three connected steps, and a brass call to action that carries the trust line.
// What you get keeps the interactive module list: hover, focus or tap a row and the panel beside it shows that module (W11-R58). Styles: the `lr-*` rules in src/styles/landing.css, tokens only (see MISSING.md).
const { t } = useI18n()
const who = ['cultural', 'religious', 'language', 'youth'] as const
const steps = [['name', '5'], ['look', '2'], ['launch', '']] as const
// The 'from' line reads the real prices (cheapest launch package, then Live per month); the built-in list stands in until the platform answers (W12-R15).
onMounted(() => { void loadPrices() })
const launchPrices = computed(() => LAUNCH_PACKAGES.map((p) => minorOf(`launch.${p.id}`)).filter((x): x is number => x !== null))
const fromLaunch = computed(() => (launchPrices.value.length ? Math.min(...launchPrices.value) : null))
const fromMonth = computed(() => minorOf('running.live.month'))
const proofStats = BCA_STATS.filter((s) => s.id !== 'launch')
</script>

<template>
  <div class="bs-land">
    <section class="bs-hero bs-sx">
      <div class="bs-hero__copy">
        <span class="rs-eyebrow">{{ t('landing.hero.eyebrow') }}</span>
        <h1 class="bs-d">{{ t('landing.hero.title') }} <em>{{ t('landing.hero.titleEm') }}</em></h1>
        <hr class="rs-rule">
        <p class="bs-lede">{{ t('landing.hero.lede') }}</p>
        <div class="bs-row lp-ctas" style="flex-wrap: wrap">
          <AppButton size="lg" icon="arrow" to="/signup">{{ t('landing.hero.primary') }}</AppButton>
          <AppButton size="lg" variant="secondary" to="/pricing">{{ t('landing.hero.secondary') }}</AppButton>
        </div>
        <p class="bs-fine">{{ t('landing.hero.trial') }}<template v-if="fromLaunch !== null && fromMonth !== null"> <span aria-hidden="true">·</span> {{ t('landing.hero.price', { launch: usd(fromLaunch), month: usd(fromMonth) }) }}</template></p>
      </div>
      <LaunchPreview />
    </section>

    <section id="features" class="bs-sx lr-sec">
      <div class="bs-head"><span class="rs-eyebrow">{{ t('landing.modules.eyebrow') }}</span><h2 class="bs-h2 lr-h2">{{ t('landing.modules.title') }}</h2></div>
      <ModuleIndex />
    </section>

    <section class="bs-sx lr-sec lr-light">
      <div class="bs-head"><span class="rs-eyebrow">{{ t('landing.who.eyebrow') }}</span><h2 class="bs-h2 lr-h2">{{ t('landing.who.title') }}</h2></div>
      <div class="lr-who">
        <div v-for="w in who" :key="w">
          <small>{{ t(`landing.who.${w}.label`) }}</small>
          <h3>{{ t(`landing.who.${w}.name`) }}</h3>
          <p>{{ t(`landing.who.${w}.text`) }}</p>
        </div>
      </div>
    </section>

    <section class="bs-sx lr-sec" aria-labelledby="proof-h">
      <div class="lr-use">
        <div>
          <span class="rs-eyebrow">{{ t('landing.proof.eyebrow') }} · BCA Oslo</span>
          <!-- MOCK: BCA Oslo figures are invented placeholders, not measured results. -->
          <div class="lr-big">{{ CASE_FIGURES.launchMinutes }}<span>{{ t('landing.proof.unit') }}</span></div>
          <h2 id="proof-h" class="lr-quote">{{ t('landing.proof.title') }}</h2>
          <p class="bs-fine"><RouterLink to="/case-study/bca">{{ t('landing.proof.link') }}</RouterLink> <span aria-hidden="true">·</span> {{ t('landing.proof.mock') }}</p>
        </div>
        <div class="lr-stats">
          <div v-for="s in proofStats" :key="s.id"><b>{{ s.value }}</b><span>{{ t(`landing.proof.stats.${s.id}`) }}</span></div>
        </div>
      </div>
    </section>

    <section class="bs-sx lr-sec lr-raise" aria-labelledby="steps-h">
      <div class="bs-head"><span class="rs-eyebrow">{{ t('landing.steps.eyebrow') }}</span><h2 id="steps-h" class="bs-h2 lr-h2">{{ t('landing.steps.title') }}</h2></div>
      <ol class="lr-steps">
        <li v-for="([id, min], i) in steps" :key="id">
          <span class="lr-steps__n">{{ i + 1 }}</span>
          <h3>{{ t(`landing.steps.${id}.name`) }}</h3>
          <p>{{ t(`landing.steps.${id}.text`) }}</p>
          <small>{{ min ? t('landing.steps.minutes', { n: min }) : t('landing.steps.click') }}</small>
        </li>
      </ol>
    </section>

    <section class="bs-sx lr-cta">
      <h2>{{ t('landing.cta.title') }}</h2>
      <p>{{ t('landing.cta.text') }}</p>
      <div class="bs-row lp-ctas" style="flex-wrap: wrap; justify-content: center">
        <AppButton size="lg" icon="arrow" to="/signup">{{ t('landing.hero.primary') }}</AppButton>
        <AppButton size="lg" variant="secondary" to="/pricing">{{ t('landing.hero.secondary') }}</AppButton>
      </div>
      <div class="lr-ticks" :aria-label="t('landing.trust.label')">
        <span><AppIcon name="check" :size="14" />{{ t('landing.trust.commission') }}</span>
        <span><AppIcon name="check" :size="14" />{{ t('landing.trust.vipps') }}</span>
        <span><AppIcon name="check" :size="14" />{{ t('landing.trust.cancel') }}</span>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* On a phone the two buttons share the full width on one line while both fit, and each takes a full line when they do not (W25-R46). */
@media (max-width: 640px) {
  .lp-ctas { gap: 12px; width: 100%; }
  .lp-ctas .rs-btn { flex: 1 1 auto; justify-content: center; }
}
</style>
