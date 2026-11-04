<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { platform, type HealthCheck, type SquareHealth } from '@/services/platform'
import { errorText } from '@/features/platform/errorText'
import { useSquare } from './squareContext'

// Health tab (W10-R19; redesigned in W23-R40 from the design project's `Square Health Redesign.html`): what the square's server says about itself, as yes/no
// states and one sentence each (ADR 038: no data, no counts). It opens with a verdict and a segmented bar (one segment per check), lifts the checks that need a
// look into their own card, and shows a dot per check in the groups. Analytics will get its own section later; the dashed note at the bottom holds its place.
const { t } = useI18n()
const { date } = useFormat()
const { sq } = useSquare()
const health = ref<SquareHealth | null>(null)
const loading = ref(true)
const error = ref('')
const checkedAt = ref<Date | null>(null)
const GROUPS = ['system', 'jobs', 'setup'] as const
const all = computed(() => health.value?.checks ?? [])
const groups = computed(() => GROUPS.map((g) => ({ g, items: all.value.filter((c: HealthCheck) => c.group === g) })).filter((x) => x.items.length))
const trouble = computed(() => all.value.filter((c) => c.state === 'warn' || c.state === 'fail'))
const count = (state: string) => all.value.filter((c) => c.state === state).length
const kind = (s: string) => (s === 'ok' ? 'ok' : s === 'warn' ? 'warn' : s === 'fail' ? 'bad' : 'off')
const verdict = computed(() => (trouble.value.length ? t('squareHealth.verdict', { n: all.value.length - trouble.value.length, total: all.value.length }) : t('portal.health.allGood')))

async function load() {
  if (!sq.value) return
  loading.value = true
  error.value = ''
  try { health.value = await platform.getSquareHealth(sq.value.id); checkedAt.value = new Date() } catch (e) { error.value = errorText(t, e) } finally { loading.value = false }
}
onMounted(load)
watch(() => sq.value?.id, load)
</script>

<template>
  <div v-if="sq" style="display: grid; gap: 14px" data-testid="health-page">
    <div class="bw-hd" style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; align-items: flex-start">
      <div><h2 class="bs-h2" style="font-size: 28px; margin: 0">{{ t('portal.health.title') }}</h2><p class="bs-mute" style="margin: 4px 0 0; font-size: var(--text-sm)">{{ t('portal.health.lede') }}</p></div>
      <AppButton icon="refresh" class="sh-btn" variant="secondary" :loading="loading" @click="load">{{ loading ? t('portal.health.checking') : t('portal.health.refresh') }}</AppButton>
    </div>

    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
    <template v-else-if="health">
      <AppAlert v-if="!health.reachable" tone="danger" :title="t('portal.health.down')">{{ t('portal.health.downBody') }}</AppAlert>

      <section class="sh-sum">
        <div class="sh-sum__t"><h3 class="sh-verdict">{{ verdict }}</h3><small v-if="checkedAt">{{ t('squareHealth.checkedAt', { time: date(checkedAt, { hour: '2-digit', minute: '2-digit' }) }) }}<template v-if="health.version"> · {{ t('portal.health.version', { v: health.version }) }}</template></small></div>
        <div class="sh-bar" aria-hidden="true"><i v-for="c in all" :key="c.key" :class="`sh-${kind(c.state)}`" /></div>
        <div class="sh-legend"><span class="sh-ok">{{ t('squareHealth.nOk', { n: count('ok') }) }}</span><span class="sh-off">{{ t('squareHealth.nOff', { n: count('off') }) }}</span><span class="sh-warn">{{ t('squareHealth.nLook', { n: trouble.length }) }}</span></div>
      </section>

      <section v-if="trouble.length" class="sh-att" :class="trouble.some((c) => c.state === 'fail') && 'sh-att--bad'" role="alert">
        <b>{{ t('portal.health.attention') }}</b>
        <span v-for="c in trouble" :key="c.key">{{ c.text }}</span>
      </section>

      <section v-for="x in groups" :key="x.g" class="sh-card" role="list">
        <h3>{{ t(`portal.health.groups.${x.g}`) }}</h3>
        <div v-for="c in x.items" :key="c.key" class="sh-ck" :class="`sh-ck--${kind(c.state)}`" role="listitem" :data-check="c.key">
          <span class="sh-dot" aria-hidden="true" />
          <p>{{ c.text }}</p>
          <span class="sh-tag">{{ t(`portal.health.states.${c.state}`) }}</span>
        </div>
      </section>
    </template>

  </div>
</template>

<style scoped>
/* Tokens only: the design's cream, rust, green and amber are mapped to the theme (brass, success, warning, danger); shapes come from shape.css. */
.sh-btn.sh-btn { padding: 0 18px; border-radius: var(--shape-control); border-color: var(--color-brass); background: transparent; color: var(--color-brass-text); font: 600 11px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; white-space: nowrap; }
.sh-btn.sh-btn:hover { background: var(--color-brass-subtle); }
.sh-sum { padding: 20px 24px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--shape-surface); }
.sh-sum__t { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.sh-verdict { margin: 0; font: 400 30px/1.15 var(--font-display); }
.sh-sum small { color: var(--color-text-muted); font-size: var(--text-xs); }
.sh-bar { display: flex; gap: 4px; margin: 14px 0 8px; }
.sh-bar i { flex: 1; height: 8px; border-radius: var(--shape-control); }
.sh-ok { --c: var(--color-success); }
.sh-warn { --c: var(--color-warning); }
.sh-bad { --c: var(--color-danger); }
.sh-off { --c: var(--color-border-strong); }
.sh-bar i { background: var(--c); }
.sh-legend { display: flex; gap: 16px; flex-wrap: wrap; font-size: var(--text-xs); color: var(--color-text-muted); }
.sh-legend span::before { content: ''; display: inline-block; width: 8px; height: 8px; margin-right: 6px; border-radius: 50%; background: var(--c); }
.sh-att { display: grid; gap: 4px; padding: 16px 20px; background: var(--color-warning-subtle); border: 1px solid var(--color-warning); border-radius: var(--shape-surface); color: var(--color-warning); font-size: var(--text-sm); }
.sh-att b { font-size: var(--text-base); }
.sh-att--bad { background: var(--color-danger-subtle); border-color: var(--color-danger); color: var(--color-danger); }
.sh-card { padding: 14px 20px 6px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--shape-surface); }
.sh-card h3 { margin: 0 0 4px; font: 600 10px var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-text-muted); }
.sh-ck { display: flex; gap: 12px; align-items: flex-start; padding: 11px 0; border-top: 1px solid var(--color-border); }
.sh-card h3 + .sh-ck { border-top: 0; }
.sh-ck p { margin: 0; flex: 1; font-size: var(--text-sm); }
.sh-dot { flex: none; width: 10px; height: 10px; margin-top: 6px; border-radius: 50%; background: var(--color-success); }
.sh-tag { padding: 3px 10px; border-radius: var(--shape-control); background: var(--color-success-subtle); color: var(--color-success); font: 600 10px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; white-space: nowrap; }
.sh-ck--warn .sh-dot { background: var(--color-warning); box-shadow: 0 0 0 4px var(--color-warning-subtle); }
.sh-ck--warn .sh-tag { background: var(--color-warning-subtle); color: var(--color-warning); }
.sh-ck--bad .sh-dot { background: var(--color-danger); box-shadow: 0 0 0 4px var(--color-danger-subtle); }
.sh-ck--bad .sh-tag { background: var(--color-danger-subtle); color: var(--color-danger); }
.sh-ck--off .sh-dot { background: var(--color-border-strong); }
.sh-ck--off .sh-tag { background: var(--color-surface-sunken); color: var(--color-text-muted); }
.sh-an { display: flex; gap: 16px; align-items: center; margin-top: 12px; padding: 18px 22px; border: 1px dashed var(--color-border-strong); border-radius: var(--shape-surface); color: var(--color-text-muted); font-size: var(--text-sm); }
.sh-an i { flex: none; display: grid; place-items: center; width: 44px; height: 44px; border-radius: var(--shape-control); background: var(--color-surface-sunken); color: var(--color-text); }
.sh-an b { display: block; color: var(--color-text); }
</style>
