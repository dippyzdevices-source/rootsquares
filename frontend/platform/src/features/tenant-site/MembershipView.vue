<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@rootsquares/ui/components/useToast'
import { joinMembership } from '@/services/api'
import TButton from './components/TButton.vue'
import TField from './components/TField.vue'

const { t, tm, rt } = useI18n()
const { push } = useToast()

const PLANS = [{ id: 'student', price: 0 }, { id: 'full', price: 400, hl: true }, { id: 'family', price: 700 }]
const perks = (id: string) => (tm(`site.plans.${id}`) as unknown[])[2] as string[]
const form = reactive({ name: '', email: '', plan: 'full' })
const touched = ref(false)
const busy = ref(false)
const sent = ref(false)
const errors = computed(() => ({
  name: form.name.trim() ? '' : t('site.joinNameError'),
  email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email) ? '' : t('site.joinEmailError'),
}))
const options = computed(() => PLANS.map((p) => ({ value: p.id, label: t(`site.plans.${p.id}[0]`) })))

function choose(id: string) { form.plan = id; document.getElementById('join')?.scrollIntoView({ behavior: 'smooth' }) }
async function submit() {
  touched.value = true
  if (errors.value.name || errors.value.email) return
  busy.value = true
  await joinMembership()
  busy.value = false
  sent.value = true
  push(t('site.joined'), 'success', t('site.joinedBody'))
}
</script>

<template>
  <section class="t-sec">
    <div class="t-wrap">
      <h1 style="font-size: clamp(32px, 5vw, 48px)">{{ t('site.plansTitle') }}</h1>
      <p class="t-muted" style="margin: 8px 0 24px">{{ t('site.plansText') }}</p>
      <div class="t-card t-memstatus">
        <span class="t-memstatus__mark" aria-hidden="true">AB</span>
        <div style="flex: 1 1 200px; min-width: 0"><div class="t-eyebrow">{{ t('site.member.status') }}</div><div class="t-strong" style="font-size: 18px">Anirban Banerjee · {{ t('site.member.plan') }}</div><div style="font-size: 15px">{{ t('site.member.until') }}</div></div>
        <span class="t-badge t-badge--ok">{{ t('site.member.active') }}</span>
      </div>
      <div class="t-plans" style="margin-top: 24px">
        <div v-for="p in PLANS" :key="p.id" class="t-card t-plan" :class="p.hl && 't-plan--hl'">
          <div class="t-row" style="justify-content: space-between">
            <h3 style="font-size: 22px">{{ t(`site.plans.${p.id}[0]`) }}</h3>
            <span v-if="p.hl" class="t-badge">{{ t('site.popular') }}</span>
          </div>
          <p class="t-muted" style="margin: 0">{{ t(`site.plans.${p.id}[1]`) }}</p>
          <div><span class="t-plan__price">{{ p.price === 0 ? t('site.free') : p.price }}</span> <span v-if="p.price" class="t-muted">{{ t('site.perYear') }}</span></div>
          <ul><li v-for="x in perks(p.id)" :key="rt(x)"><span aria-hidden="true">✓ </span>{{ rt(x) }}</li></ul>
          <div style="margin-top: auto"><TButton :variant="p.hl ? 'primary' : 'outline'" block @click="choose(p.id)">{{ t('site.join') }}</TButton></div>
        </div>
      </div>
    </div>
  </section>
  <section id="join" class="t-sec" style="padding-top: 0">
    <div class="t-wrap" style="max-width: 640px">
      <div class="t-card">
        <div v-if="sent" class="t-stack"><h2 style="font-size: 26px">{{ t('site.joined') }}</h2><p>{{ t('site.joinedBody') }}</p></div>
        <form v-else class="t-stack" novalidate @submit.prevent="submit">
          <h2 style="font-size: 26px">{{ t('site.joinTitle') }}</h2>
          <TField v-model="form.name" :label="t('site.joinName')" autocomplete="name" :error="touched ? errors.name : ''" />
          <TField v-model="form.email" type="email" :label="t('site.joinEmail')" autocomplete="email" :error="touched ? errors.email : ''" />
          <TField v-model="form.plan" as="select" :label="t('site.joinPlan')" :options="options" />
          <div><TButton type="submit" :disabled="busy">{{ t('site.joinSend') }}</TButton></div>
        </form>
      </div>
    </div>
  </section>
</template>
