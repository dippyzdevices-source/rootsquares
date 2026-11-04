<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { squareEmailLink, squareGoogle, squareSignOut, squareToken } from '@/services/squareAuth'
import { useI18n } from 'vue-i18n'
import ThemeScope from '@/components/ui/ThemeScope.vue'
import { ApiError, platform, type PublicSquare, type SquareMe } from '@/services/platform'
import { DEFAULT_TENANT_THEME, getTheme } from '@rootsquares/ui/themes'
import '@/features/tenant-site/tenant.css'

// Hello-world page of a square (no sign-in): served from the platform for any ready square, themed with the square's theme, and it reads one fact
// from the square's OWN database to show the wiring. The real square site replaces this later.
// Either `slug` (the platform route /s/<slug>) or `host` (the browser is on the square's own host name) says which square this is.
const props = defineProps<{ slug?: string; host?: string }>()
const { t } = useI18n()
const sq = ref<PublicSquare | null>(null)
const missing = ref(false)
const loading = ref(true)

const me = ref<SquareMe | null>(null)
const email = ref('')
const linkSent = ref(false)
const authError = ref('')
const busy = ref(false)
const returnTo = () => (props.host ? `${window.location.origin}${window.location.pathname}` : `${window.location.origin}/s/${props.slug}`)

// Who is signed in to this square? A token of the square's own auth project, checked by the platform against that project's keys.
async function whoAmI() {
  const s = sq.value
  if (!s?.auth_url || !s.auth_public_key) return
  const token = await squareToken(s.auth_url, s.auth_public_key)
  if (!token) { me.value = null; return }
  try { me.value = await platform.getSquareMe(s.slug, token) } catch { me.value = null; authError.value = t('plat.hello.invalidSession') }
}

onMounted(async () => {
  try {
    sq.value = props.host ? await platform.getPublicSquareByHost(props.host) : await platform.getPublicSquare(props.slug ?? '')
    await whoAmI()
  } catch (e) {
    missing.value = e instanceof ApiError && e.status === 404
  }
  loading.value = false
})

async function sendLink() {
  const s = sq.value
  if (!s?.auth_url || !s.auth_public_key) return
  busy.value = true; authError.value = ''
  try { await squareEmailLink(s.auth_url, s.auth_public_key, email.value.trim(), returnTo()); linkSent.value = true } catch { authError.value = t('plat.hello.signInFailed') }
  busy.value = false
}
async function google() {
  const s = sq.value
  if (!s?.auth_url || !s.auth_public_key) return
  authError.value = ''
  try { await squareGoogle(s.auth_url, s.auth_public_key, returnTo()) } catch { authError.value = t('plat.hello.signInFailed') }
}
async function signOut() {
  const s = sq.value
  if (s?.auth_url && s.auth_public_key) await squareSignOut(s.auth_url, s.auth_public_key)
  me.value = null; linkSent.value = false
}
const themeName = (id: string) => getTheme(id)?.name ?? id
</script>

<template>
  <ThemeScope :theme="sq?.theme_id ?? DEFAULT_TENANT_THEME" mode="light">
    <div class="t-root" style="min-height: 100vh; display: grid; place-items: center; padding: 24px">
      <main id="t-main" style="max-width: 640px; width: 100%; display: grid; gap: 24px">
        <p v-if="loading" style="color: var(--t-text-muted); margin: 0">…</p>
        <template v-else-if="sq">
          <header style="display: grid; gap: 8px">
            <h1 style="font-size: 56px; line-height: 1.05">{{ t('plat.hello.title') }}</h1>
            <p style="margin: 0; color: var(--t-text-muted)">{{ t('plat.hello.from', { name: sq.name }) }}</p>
          </header>
          <dl style="display: grid; grid-template-columns: max-content 1fr; gap: 10px 24px; margin: 0; padding: 20px; background: var(--t-surface); border: var(--t-border-w) solid var(--t-border); border-radius: var(--t-radius)">
            <dt style="color: var(--t-text-muted)">{{ t('plat.hello.address') }}</dt><dd style="margin: 0; overflow-wrap: anywhere">{{ sq.domain }}</dd>
            <dt style="color: var(--t-text-muted)">{{ t('plat.hello.theme') }}</dt><dd style="margin: 0">{{ themeName(sq.theme_id) }}</dd>
            <dt style="color: var(--t-text-muted)">{{ t('plat.hello.database') }}</dt>
            <dd style="margin: 0">{{ sq.database.ok ? t(sq.database.admins === 1 ? 'plat.hello.dbOk' : 'plat.hello.dbOkMany', { n: sq.database.admins ?? 0 }) : t('plat.hello.dbDown') }}</dd>
            <dt style="color: var(--t-text-muted)">{{ t('plat.hello.auth') }}</dt><dd style="margin: 0">{{ sq.has_auth_project ? t('plat.hello.authYes') : t('plat.hello.authNo') }}</dd>
            <dt style="color: var(--t-text-muted)">{{ t('plat.hello.google') }}</dt><dd style="margin: 0">{{ sq.google_login === 'enabled' ? t('plat.hello.googleOn') : t('plat.hello.googleSoon') }}</dd>
          </dl>
          <section v-if="sq.auth_url" style="display: grid; gap: 12px; padding: 20px; background: var(--t-surface); border: var(--t-border-w) solid var(--t-border); border-radius: var(--t-radius)">
            <template v-if="me">
              <h2 style="font-size: 22px">{{ t('plat.hello.signedInAs', { email: me.email }) }}</h2>
              <p style="margin: 0; color: var(--t-text-muted)">{{ me.is_admin ? t('plat.hello.roleAdmin', { role: me.role }) : t('plat.hello.roleMember') }}</p>
              <p style="margin: 0"><button type="button" class="t-btn t-btn--outline" @click="signOut">{{ t('plat.hello.signOut') }}</button></p>
            </template>
            <template v-else>
              <h2 style="font-size: 22px">{{ t('plat.hello.signInTitle') }}</h2>
              <p v-if="authError" role="alert" style="margin: 0; color: var(--t-danger, var(--t-text-strong))">{{ authError }}</p>
              <p v-if="linkSent" style="margin: 0">{{ t('plat.hello.linkSent') }}</p>
              <form v-else style="display: grid; gap: 10px" @submit.prevent="sendLink">
                <label for="sq-email" style="color: var(--t-text-muted)">{{ t('plat.login.email') }}</label>
                <input id="sq-email" v-model="email" type="email" autocomplete="email" required style="min-height: var(--t-control-h); padding: 8px 12px; border: var(--t-border-w) solid var(--t-border); border-radius: var(--t-radius); background: var(--t-bg); color: var(--t-text); font: inherit">
                <button type="submit" class="t-btn" :disabled="busy || !email.trim()">{{ t('plat.hello.sendLink') }}</button>
              </form>
              <button v-if="sq.google_login === 'enabled'" type="button" class="t-btn t-btn--outline" @click="google">{{ t('plat.google.login') }}</button>
              <p v-else style="margin: 0; color: var(--t-text-muted); font-size: 14px">{{ t('plat.hello.googleSoon') }}</p>
            </template>
          </section>
        </template>
        <header v-else style="display: grid; gap: 8px">
          <h1 style="font-size: 40px">{{ missing ? t('plat.hello.notFoundTitle') : t('plat.errors.generic') }}</h1>
          <p v-if="missing" style="margin: 0; color: var(--t-text-muted)">{{ t('plat.hello.notFoundText') }}</p>
        </header>
        <p v-if="!host" style="margin: 0"><RouterLink to="/" class="t-btn t-btn--outline">{{ t('plat.hello.back') }}</RouterLink></p>
      </main>
    </div>
  </ThemeScope>
</template>
