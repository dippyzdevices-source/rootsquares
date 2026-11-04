<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import StateGate from '@rootsquares/ui/components/StateGate.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { platform, type PlatformSquare } from '@/services/platform'
import { useAuthStore } from '@/stores/auth'
import { errorText } from './errorText'
import SquareStatusChip from './SquareStatusChip.vue'
import AttentionStrip from '@/features/portal/AttentionStrip.vue'

// Dashboard: my squares as boxes in a grid, like the projects page of Supabase (W11-R66), and their status. Polls every 2 s while a square is still provisioning.
// The cards follow option A of the user's design 'Your Squares Ideas' (W26-R26), in the theme's own colours and sizes: the logo with a green dot when the square is ready (a
// label only for the other states), the name with its address under it, the date and 'Open' at the foot, and a dashed 'Create square' box at the end.
const { t } = useI18n()
const { date } = useFormat()
const auth = useAuthStore()
const squares = ref<PlatformSquare[]>([])
const loading = ref(true)
const error = ref('')
let timer: ReturnType<typeof setInterval> | undefined

async function load() {
  try { squares.value = await platform.listSquares(); error.value = '' } catch (e) { error.value = errorText(t, e) }
  loading.value = false
  const busy = squares.value.some((s) => s.status === 'provisioning' && !s.awaiting_payment)
  if (busy && !timer) timer = setInterval(load, 2000)
  if (!busy && timer) { clearInterval(timer); timer = undefined }
}
onMounted(load)
onBeforeUnmount(() => clearInterval(timer))
// The squares of every organisation the person belongs to, grouped under the organisation's name (W26-R27). A person can belong to several; the server lists them all.
const groups = computed(() => {
  const by = new Map<string, { id: string; name: string; squares: PlatformSquare[] }>()
  for (const s of squares.value) {
    const g = by.get(s.org_id) ?? { id: s.org_id, name: s.org_name ?? '', squares: [] }
    g.squares.push(s)
    by.set(s.org_id, g)
  }
  return [...by.values()]
})
const state = computed(() => (loading.value ? 'loading' : error.value ? 'error' : squares.value.length ? 'default' : 'empty'))
</script>

<template>
  <section class="mk-sec"><div class="au-col" style="max-width: none">
    <header class="bs-row" style="justify-content: space-between; flex-wrap: wrap; gap: 12px">
      <div style="display: grid; gap: 8px">
        <h1 class="bs-d" style="font-size: 40px">{{ t('plat.dashboard.title') }}</h1>
        <p class="bs-lede" style="font-size: var(--text-base)">{{ t('plat.dashboard.sub') }}</p>
      </div>
      <AppButton icon="plus" to="/squares/new">{{ t('plat.dashboard.create') }}</AppButton>
    </header>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
    <AttentionStrip />
    <StateGate :state="state" :rows="3" :empty-title="t('plat.dashboard.emptyTitle')" :empty-text="t('plat.dashboard.emptyText')" @retry="load">
      <div class="sq-orgs">
      <section v-for="(g, gi) in groups" :key="g.id" class="sq-org">
      <h2 v-if="g.name && groups.length > 1" class="sq-org__name">{{ g.name }}</h2>
      <div class="sq-grid">
        <RouterLink v-for="s in g.squares" :key="s.id" :to="`/squares/${s.id}`" class="sq-card">
          <span class="sq-card__top">
            <span class="sq-logo-wrap">
              <span class="sq-logo" aria-hidden="true">
                <template v-if="s.logo_url">
                  <img :src="s.logo_url" alt="" class="sq-logo__img" :class="s.logo_dark_url && 'sq-logo__img--light'">
                  <img v-if="s.logo_dark_url" :src="s.logo_dark_url" alt="" class="sq-logo__img sq-logo__img--dark">
                </template>
                <template v-else>{{ s.name.trim().charAt(0).toUpperCase() }}</template>
              </span>
              <span v-if="s.status === 'ready'" class="sq-dot" role="img" :aria-label="t('plat.status.ready')" />
            </span>
            <SquareStatusChip :status="s.status" :awaiting-payment="s.awaiting_payment" />
          </span>
          <span class="sq-card__who">
            <b class="sq-card__name">{{ s.name }}</b>
            <span class="sq-card__s">{{ s.domain }}</span>
          </span>
          <span class="sq-card__foot">
            <span class="sq-card__s">{{ t('plat.dashboard.colCreated') }} {{ date(s.created_at, { day: 'numeric', month: 'short', year: 'numeric' }) }}</span>
            <b class="sq-card__open">{{ t('plat.dashboard.open') }} <AppIcon name="arrow" :size="14" /></b>
          </span>
        </RouterLink>
        <RouterLink v-if="gi === groups.length - 1" to="/squares/new" class="sq-add"><span class="sq-add__plus" aria-hidden="true">+</span>{{ t('plat.dashboard.create') }}</RouterLink>
      </div>
      </section>
      </div>
    </StateGate>
    <p v-if="auth.user" class="bs-mute" style="margin: 0; font-size: var(--text-xs)">{{ auth.user.email }} · <template v-if="auth.user.organizations.length === 1">{{ auth.user.organizations[0]!.name }} · </template><RouterLink to="/account" style="text-decoration: underline; text-underline-offset: 3px">{{ t('plat.account.link') }}</RouterLink></p>
  </div></section>
</template>
