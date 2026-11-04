<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import OcPill from '@rootsquares/ui/components/OcPill.vue'
import StateGate from '@rootsquares/ui/components/StateGate.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/errorText'
import { type OwnerAuditItem } from '../adminTypes'
import { adminApi as platform } from '@/adminApi'

// History tab of the owner console's square page (W13-R18): the audit log of this one square, laid out like the Audit log page (time on two lines, the event,
// who did it, a pill with the kind), 25 at a time with Load more, so it can grow without making the page long.
const props = defineProps<{ squareId: string }>()
const { t } = useI18n()
const { date } = useFormat()
const items = ref<OwnerAuditItem[]>([])
const next = ref<string | null>(null)
const loading = ref(true)
const more = ref(false)
const error = ref('')
const GROUPS = ['auth', 'square', 'admin', 'account', 'org']
const TONE: Record<string, 'ok' | 'warn' | 'info' | 'bad' | 'mute'> = { auth: 'info', square: 'ok', admin: 'warn', account: 'info', org: 'info' }
const kind = (action: string) => action.split('.')[0] ?? ''

async function load(append = false) {
  if (append) more.value = true; else loading.value = true
  try {
    const page = await platform.ownerAudit({ square_id: props.squareId, before: append ? next.value ?? undefined : undefined, limit: 25 })
    items.value = append ? [...items.value, ...page.items] : page.items
    next.value = page.next_before
    error.value = ''
  } catch (e) { error.value = errorText(t, e) }
  loading.value = false; more.value = false
}
onMounted(() => load())
const state = computed(() => (loading.value ? 'loading' : error.value ? 'error' : items.value.length ? 'default' : 'empty'))
const day = (iso: string) => date(iso, { day: 'numeric', month: 'short', year: 'numeric' })
const time = (iso: string) => date(iso, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const hasData = (d: Record<string, unknown>) => Object.keys(d).length > 0
</script>

<template>
  <div style="display: grid; gap: 12px">
    <div class="bs-row" style="justify-content: flex-end"><RouterLink :to="`/audit?square=${squareId}`" style="font-size: var(--text-sm)">{{ t('own.audit.viewAll') }}</RouterLink></div>
    <StateGate :state="state" :rows="5" :empty-title="t('own.audit.emptyTitle')" :empty-text="t('own.audit.emptyText')" @retry="load()">
      <div class="oc-card">
        <table class="oc-tbl oc-tbl--fixed">
          <colgroup><col class="c-when"><col class="c-event"><col class="c-actor"><col class="c-type"></colgroup>
          <thead>
            <tr><th>{{ t('own.audit.colWhen') }}</th><th>{{ t('own.audit.colAction') }}</th><th>{{ t('own.audit.colActor') }}</th><th>{{ t('own.audit.colType') }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="e in items" :key="e.id">
              <td class="nl oc-mut" :data-label="t('own.audit.colWhen')">{{ day(e.at) }}<br>{{ time(e.at) }}</td>
              <td class="pri" :data-label="t('own.audit.colAction')">
                <b style="font-weight: 500; overflow-wrap: anywhere">{{ e.action }}</b>
                <details v-if="hasData(e.data)" class="oc-det"><summary>{{ t('own.audit.details') }}</summary><code>{{ JSON.stringify(e.data) }}</code></details>
              </td>
              <td :data-label="t('own.audit.colActor')">
                <RouterLink v-if="e.actor_id && e.actor_kind !== 'staff'" :to="`/people/${e.actor_id}`">{{ e.actor_email ?? e.actor_id.slice(0, 8) }}</RouterLink>
                <span v-else-if="e.actor_id">{{ e.actor_email ?? e.actor_id.slice(0, 8) }} <small class="oc-mut">({{ t('own.audit.staff') }})</small></span>
                <span v-else class="oc-mut">{{ t('own.audit.noActor') }}</span>
              </td>
              <td :data-label="t('own.audit.colType')">
                <OcPill :tone="TONE[kind(e.action)] ?? 'mute'">{{ GROUPS.includes(kind(e.action)) ? t(`own.audit.groups.${kind(e.action)}`) : kind(e.action) }}</OcPill>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="next" class="oc-more"><button type="button" class="oc-btn" :disabled="more" @click="load(true)"><AppIcon name="chevron-down" :size="14" />{{ more ? t('own.audit.loading') : t('own.audit.more') }}</button></div>
    </StateGate>
  </div>
</template>
