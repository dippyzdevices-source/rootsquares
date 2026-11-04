<script setup lang="ts">
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import OcHead from '@/components/OcHead.vue'
import OcPill from '@rootsquares/ui/components/OcPill.vue'
import { errorText } from '@/errorText'
import { type OwnerUserDetail } from '../adminTypes'
import { adminApi as platform } from '@/adminApi'

// Admin console, one customer account (staff only): organisations and squares, sign out everywhere. Staff are not made from customer accounts (ADR 083).
// Built in W13-R32 from the same blocks as the People list (OcHead, oc-card, oc-li, avatar, OcPill, oc-btn): there is no design of its own for this page.
const { t } = useI18n()
const route = useRoute()
const user = ref<OwnerUserDetail | null>(null)
const error = ref('')
const notice = ref('')
const busy = ref('')
const dialog = ref<'' | 'logout'>('')
const TONE = { ready: 'ok', provisioning: 'warn', failed: 'bad' } as const
const initials = (name: string) => name.split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join('')

async function load() {
  try { user.value = await platform.ownerUser(String(route.params.id)); error.value = '' } catch (e) { error.value = errorText(t, e) }
}
onMounted(load)

async function run(name: string, fn: () => Promise<string | void>) {
  dialog.value = ''; busy.value = name; notice.value = ''; error.value = ''
  try { notice.value = (await fn()) ?? ''; await load() } catch (e) { error.value = errorText(t, e) }
  busy.value = ''
}
const logout = () => run('logout', async () => { if (user.value) return t('own.people.logoutDone', { n: await platform.logoutUser(user.value.id) }) })
</script>

<template>
  <div class="oc-back">
    <nav :aria-label="t('own.people.crumb')"><ol class="rs-crumbs"><li><RouterLink class="oc-crumb" to="/people">{{ t('own.people.back') }}</RouterLink><span aria-hidden="true">/</span></li><li v-if="user" aria-current="page">{{ user.name || user.email }}</li></ol></nav>
    <AppButton to="/people" variant="secondary" size="sm" icon="chevron-left">{{ t('own.people.backBtn') }}</AppButton>
  </div>
  <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
  <AppAlert v-if="notice" tone="success">{{ notice }}</AppAlert>
  <template v-if="user">
    <OcHead :title="user.name || user.email" :sub="`${user.email} · ${user.sign_in}`" />
    <section class="oc-card">
      <h3 class="oc-h3">{{ t('own.people.orgs') }}</h3>
      <p v-if="!user.orgs.length" class="oc-mut" style="margin: 0; padding: 24px 18px">{{ t('own.people.noOrgs') }}</p>
      <div v-for="o in user.orgs" :key="o.id" class="oc-li" style="align-items: flex-start">
        <div class="oc-nm"><span class="oc-av">{{ initials(o.name) }}</span><div><b>{{ o.name }}</b><small>{{ o.role }}</small></div></div>
        <div class="oc-stack" style="align-items: flex-end">
          <span v-if="!o.squares.length" class="oc-mut">{{ t('own.people.noSquares') }}</span>
          <span v-for="s in o.squares" :key="s.id" class="oc-row"><RouterLink :to="`/squares/${s.id}`" class="oc-link">{{ s.name }}</RouterLink><OcPill :tone="s.awaiting_payment ? 'warn' : TONE[s.status]">{{ s.awaiting_payment ? t('plat.status.awaiting') : t(`plat.owner.st.${s.status}`) }}</OcPill></span>
        </div>
      </div>
    </section>
    <section class="oc-card">
      <h3 class="oc-h3">{{ t('own.people.actions') }}<RouterLink :to="`/audit?actor=${user.id}`" class="oc-link" style="text-transform: none; letter-spacing: 0; font-size: var(--text-sm); font-weight: 400">{{ t('own.audit.viewActor') }}</RouterLink></h3>
      <div class="oc-row" style="padding: 16px 18px">
        <button type="button" class="oc-btn" :disabled="busy === 'logout'" @click="dialog = 'logout'"><AppIcon name="out" :size="14" />{{ t('own.people.logout') }}</button>
      </div>
    </section>
    <ConfirmDialog v-if="dialog === 'logout'" :title="t('own.people.logoutTitle', { email: user.email })" :body="t('own.people.logoutText')" icon="out" :verb="t('own.people.logout')" @cancel="dialog = ''" @confirm="logout" />
  </template>
</template>
