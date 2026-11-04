<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { platform, type PlatformSquare } from '@/services/platform'
import { useAuthStore } from '@/stores/auth'

// The sign-in component of the site header (W10-R22). Signed out: Sign in and Start free. Signed in: a button with the person's name that opens a panel with
// their roles (the role in each organisation), then Square (Your squares, then each square they own, opening
// its portal), then Sign out. `inline` lays the same panel out as a list for the phone menu.
const props = defineProps<{ inline?: boolean }>()
const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const { push } = useToast()
const open = ref(false)
const root = ref<HTMLElement | null>(null)
const btn = ref<HTMLButtonElement | null>(null)
const panelId = useId()
const squares = ref<PlatformSquare[]>([])
const loadingSquares = ref(false)
const loaded = ref(false)

const user = computed(() => auth.user)
const label = computed(() => user.value?.name?.trim() || user.value?.email || '')
const roles = computed(() => {
  const u = user.value
  if (!u) return []
  const out: { key: string; text: string }[] = []
  for (const o of u.organizations) out.push({ key: o.id, text: t('plat.account.orgRole', { role: o.role, org: o.name }) })
  return out
})

async function loadSquares() {
  if (loaded.value || !user.value) return
  loadingSquares.value = true
  try { squares.value = await platform.listSquares(); loaded.value = true } catch { squares.value = [] } finally { loadingSquares.value = false }
}
const items = () => [...(root.value?.querySelectorAll<HTMLElement>('[role=menuitem]') ?? [])]
async function show() {
  open.value = true
  document.addEventListener('mousedown', outside)
  void loadSquares()
  await nextTick()
  items()[0]?.focus()
}
function hide(refocus = true) {
  open.value = false
  document.removeEventListener('mousedown', outside)
  if (refocus) btn.value?.focus()
}
const outside = (e: MouseEvent) => { if (root.value && !root.value.contains(e.target as Node)) hide(false) }
function onKey(e: KeyboardEvent) {
  const els = items()
  const i = els.indexOf(document.activeElement as HTMLElement)
  if (e.key === 'Escape') { e.preventDefault(); hide() }
  else if (e.key === 'ArrowDown') { e.preventDefault(); els[(i + 1) % els.length]?.focus() }
  else if (e.key === 'ArrowUp') { e.preventDefault(); els[(i - 1 + els.length) % els.length]?.focus() }
  else if (e.key === 'Home') { e.preventDefault(); els[0]?.focus() }
  else if (e.key === 'End') { e.preventDefault(); els[els.length - 1]?.focus() }
  else if (e.key === 'Tab') hide(false)
}
async function go(path: string) { hide(false); await router.push(path) }
async function signOut() {
  hide(false)
  await auth.logout()
  push(t('plat.nav.signedOut'), 'info')
  await router.push('/')
}
onBeforeUnmount(() => document.removeEventListener('mousedown', outside))
if (props.inline) void loadSquares()
</script>

<template>
  <template v-if="!user">
    <i v-if="!inline" class="pt-sep" aria-hidden="true" />
    <AppButton icon="key" variant="ghost" to="/login">{{ t('nav.signIn') }}</AppButton>
    <AppButton icon="plus" to="/signup">{{ t('nav.startFree') }}</AppButton>
  </template>

  <template v-else>
  <!-- In the header capsule (W26-R33): the person's full name with the green signed-in dot, which opens the menu. Sign out is in that menu only (W26-R35, the user's decision). -->
  <i v-if="!inline" class="pt-sep" aria-hidden="true" />
  <div ref="root" class="acm" :class="{ 'acm--inline': inline }" data-testid="account-menu">
    <button v-if="!inline" ref="btn" type="button" class="pt-name" aria-haspopup="menu" :aria-expanded="open" :aria-controls="open ? panelId : undefined" @click="open ? hide() : show()">
      <i class="pt-name__dot" aria-hidden="true" /><span class="acm-name">{{ label }}</span><AppIcon :name="open ? 'chevron-up' : 'chevron-down'" :size="14" />
    </button>
    <div v-if="open || inline" :id="panelId" class="acm-pop" role="menu" @keydown="onKey">
      <div class="acm-who"><b>{{ label }}</b><small v-if="user.name && user.email">{{ user.email }}</small></div>

      <span class="acm-h">{{ t('plat.account.roles') }}</span>
      <ul v-if="roles.length" class="acm-roles"><li v-for="r in roles" :key="r.key" class="rs-chip rs-chip--info">{{ r.text }}</li></ul>
      <small v-else class="acm-mute">{{ t('plat.account.noRoles') }}</small>

      <hr>
      <span class="acm-h">{{ t('plat.account.square') }}</span>
      <button type="button" role="menuitem" @click="go('/dashboard')"><AppIcon name="home" :size="14" />{{ t('portal.nav.squares') }}</button>
      <small v-if="loadingSquares" class="acm-mute">{{ t('plat.account.loading') }}</small>
      <button v-for="s in squares" :key="s.id" type="button" role="menuitem" @click="go(`/squares/${s.id}`)"><AppIcon name="grid" :size="14" />{{ s.name }}</button>
      <small v-if="loaded && !squares.length" class="acm-mute">{{ t('plat.account.noSquares') }}</small>

      <hr>
      <button type="button" role="menuitem" @click="signOut"><AppIcon name="x" :size="14" />{{ t('plat.nav.signOut') }}</button>
    </div>
  </div>
  </template>
</template>

<style scoped>
.acm { position: relative; }
.acm-btn { max-width: 220px; }
.acm-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.acm-pop { position: absolute; inset-inline-end: 0; top: calc(100% + 6px); z-index: 20; width: min(300px, 90vw); padding: 10px; display: grid; gap: 4px; border: 1px solid var(--color-border-strong); border-radius: var(--shape-surface); background: var(--color-surface); box-shadow: var(--shadow-md); }
.acm--inline .acm-pop { position: static; width: auto; box-shadow: none; border: 0; padding: 0; background: transparent; }
.acm-who { display: grid; padding: 2px 6px 8px; border-bottom: 1px solid var(--color-border); }
.acm-who b { font-weight: 500; overflow-wrap: anywhere; }
.acm-who small, .acm-mute { color: var(--color-text-muted); font-size: var(--text-xs); overflow-wrap: anywhere; }
.acm-mute { padding: 2px 10px; }
.acm-h { margin-top: 8px; padding: 0 6px; font-size: var(--text-xs); letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-text-muted); }
.acm-roles { list-style: none; margin: 0; padding: 0 6px; display: flex; flex-wrap: wrap; gap: 6px; }
.acm-roles li { text-transform: none; }
.acm-pop button { all: unset; box-sizing: border-box; display: flex; gap: 8px; align-items: center; min-height: 36px; padding: 0 10px; border-radius: var(--shape-inner); font-size: var(--text-sm); color: var(--color-text); cursor: pointer; overflow-wrap: anywhere; }
.acm-pop button:hover, .acm-pop button:focus-visible { background: var(--color-accent-subtle); }
.acm-pop button:focus-visible { outline: 2px solid var(--color-focus-ring, var(--color-brass)); outline-offset: -2px; }
.acm-pop hr { border: 0; border-top: 1px solid var(--color-border); margin: 6px 0 2px; width: 100%; }
@media (max-width: 760px) { .acm-pop button { min-height: 44px; } }
</style>
