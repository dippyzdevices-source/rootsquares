<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import StateGate from '@rootsquares/ui/components/StateGate.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import OcPill from '@rootsquares/ui/components/OcPill.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import OcHead from '@/components/OcHead.vue'
import { errorText } from '@/errorText'
import { type OwnerAttention, type OwnerAttentionList } from '../adminTypes'
import { adminApi as platform } from '@/adminApi'
import { attentionLink } from './attentionLink'

// "Needs attention" (W25-R33): the one list of what waits for a person at rootsquares, from GET /owner/attention (the same list gives the side bar badge).
// Built like the other console lists: OcHead, an oc-card with oc-li rows, the console pills, a small secondary button. Own sending domain asked for or help asked,
// support access granted and not opened, Google sign-in, failed squares. An item goes when it is handled.
const { t } = useI18n()
const { date } = useFormat()
const data = ref<OwnerAttentionList | null>(null)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  try { data.value = await platform.ownerAttention(); error.value = '' } catch (e) { error.value = errorText(t, e) }
  loading.value = false
}
onMounted(load)
const state = computed(() => (loading.value ? 'loading' : error.value ? 'error' : 'default'))
// A category pill beside the name so a domain request and a sign-in item scan apart (Sending Domain Redesign.html, W25-R36).
const CATEGORY: Record<OwnerAttention['kind'], { key: string; tone: 'ok' | 'warn' | 'info' | 'bad' | 'mute' }> = {
  failed: { key: 'provisioning', tone: 'bad' },
  stuck: { key: 'provisioning', tone: 'warn' },
  google_requested: { key: 'signin', tone: 'mute' },
  mail_domain_requested: { key: 'sendingDomain', tone: 'warn' },
  mail_domain_help: { key: 'sendingDomain', tone: 'warn' },
  site_domain_requested: { key: 'websiteDomain', tone: 'warn' },
  site_domain_help: { key: 'websiteDomain', tone: 'warn' },
  support_granted: { key: 'support', tone: 'info' },
}
const day = (iso: string) => date(iso, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
</script>

<template>
  <StateGate :state="state" :rows="3" empty-title="" empty-text="" @retry="load">
    <template v-if="data">
      <OcHead :title="t('own.attention.title')" :sub="t('own.attention.intro')" />
      <section class="oc-card">
        <div v-if="!data.items.length" class="oc-li" data-testid="attention-empty">
          <div class="oc-row"><AppIcon name="check" :size="20" /><div><b>{{ t('own.attention.allClearTitle') }}</b><small>{{ t('own.attention.allClearText') }}</small></div></div>
        </div>
        <div v-for="a in data.items" :key="`${a.kind}-${a.square_id}`" class="oc-li" :data-testid="`attention-${a.kind}`">
          <div>
            <span class="oc-row"><b>{{ a.name }}</b><OcPill :tone="CATEGORY[a.kind].tone">{{ t(`own.attention.cat.${CATEGORY[a.kind].key}`) }}</OcPill></span>
            <small>{{ t(`own.attention.kind.${a.kind}`) }}<template v-if="a.detail"> · {{ a.detail }}</template> · {{ day(a.since) }}</small>
          </div>
          <AppButton icon="arrow" variant="secondary" size="sm" :to="attentionLink(a)">{{ t('own.attention.open') }}</AppButton>
        </div>
      </section>
    </template>
  </StateGate>
</template>
