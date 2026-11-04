<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import OcHead from '@/components/OcHead.vue'
import OcPill from '@rootsquares/ui/components/OcPill.vue'
import StateGate from '@rootsquares/ui/components/StateGate.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/errorText'
import { type OwnerAuditItem } from '../adminTypes'
import { adminApi as platform } from '@/adminApi'

// Owner console, Audit log (platform admin only), from GET /owner/audit. ?square=<id> or ?actor=<id> narrows it to one square or person.
// Restyled in W11-R75 from "Console Audit Log.html": the time on two lines, the event with what it was about, who did it, and a pill with the kind.
const { t } = useI18n()
const { date } = useFormat()
const route = useRoute()
const router = useRouter()
const items = ref<OwnerAuditItem[]>([])
const next = ref<string | null>(null)
const loading = ref(true)
const more = ref(false)
const error = ref('')
const group = ref('')
const GROUPS = ['auth', 'square', 'admin', 'account', 'org']
const TONE: Record<string, 'ok' | 'warn' | 'info' | 'bad' | 'mute'> = { auth: 'info', square: 'ok', admin: 'warn', account: 'info', org: 'info' }
const squareId = computed(() => String(route.query.square ?? ''))
const actorId = computed(() => String(route.query.actor ?? ''))

async function load(append = false) {
  if (append) more.value = true; else loading.value = true
  try {
    const page = await platform.ownerAudit({
      action_prefix: group.value ? `${group.value}.` : undefined, square_id: squareId.value || undefined, actor_id: actorId.value || undefined,
      before: append ? next.value ?? undefined : undefined, limit: 50,
    })
    items.value = append ? [...items.value, ...page.items] : page.items
    next.value = page.next_before
    error.value = ''
  } catch (e) { error.value = errorText(t, e) }
  loading.value = false; more.value = false
}
onMounted(() => load())
watch([group, squareId, actorId], () => load())
const state = computed(() => (loading.value ? 'loading' : error.value ? 'error' : items.value.length ? 'default' : 'empty'))
const day = (iso: string) => date(iso, { day: 'numeric', month: 'short', year: 'numeric' })
const time = (iso: string) => date(iso, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const hasData = (d: Record<string, unknown>) => Object.keys(d).length > 0
const kind = (action: string) => action.split('.')[0] ?? ''
// A sentence for the event; an action that has no words yet is made readable from its name ("admin.seed_unchanged" becomes "Admin seed unchanged").
function eventText(action: string): string {
  const key = `own.audit.events.${action.replace(/\./g, '_')}`
  const text = t(key)
  if (text !== key) return text
  const plain = action.replace(/[._]/g, ' ')
  return plain.charAt(0).toUpperCase() + plain.slice(1)
}
// What it was about: "Square" with a link, "Person" with a link, the other kinds by name; the short id is for the Details only.
function entityText(entity: string): string {
  const key = `own.audit.entities.${entity}`
  const text = t(key)
  return text === key ? entity : text
}
</script>

<template>
  <OcHead :title="t('own.audit.title')" :sub="t('own.audit.sub')" />
  <div class="oc-tools">
    <label class="oc-fld">
      <select v-model="group" :aria-label="t('own.audit.group')">
        <option value="">{{ t('own.audit.all') }}</option>
        <option v-for="g in GROUPS" :key="g" :value="g">{{ t(`own.audit.groups.${g}`) }}</option>
      </select>
    </label>
    <span v-if="squareId || actorId" class="oc-row">
      <span class="oc-mut">{{ squareId ? t('own.audit.filteredSquare') : t('own.audit.filteredActor') }}</span>
      <button type="button" class="oc-btn oc-btn--g" @click="router.push('/audit')"><AppIcon name="x" :size="14" />{{ t('own.audit.clear') }}</button>
    </span>
  </div>
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
              <b style="font-weight: 500; overflow-wrap: anywhere">{{ eventText(e.action) }}</b>
              <div v-if="e.entity" class="oc-mut" style="overflow-wrap: anywhere">
                <RouterLink v-if="e.entity === 'square' && e.entity_id" :to="`/squares/${e.entity_id}`">{{ entityText(e.entity) }}: {{ t('own.audit.open') }}</RouterLink>
                <RouterLink v-else-if="e.entity === 'user' && e.entity_id" :to="`/people/${e.entity_id}`">{{ entityText(e.entity) }}: {{ t('own.audit.open') }}</RouterLink>
                <template v-else>{{ entityText(e.entity) }}</template>
              </div>
              <details v-if="hasData(e.data) || e.entity_id" class="oc-det"><summary>{{ t('own.audit.details') }}</summary><code>{{ e.action }}{{ e.entity_id ? ` · ${e.entity_id}` : '' }}{{ hasData(e.data) ? ` · ${JSON.stringify(e.data)}` : '' }}</code></details>
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
</template>
