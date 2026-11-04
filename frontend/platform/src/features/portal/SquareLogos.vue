<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import { platform } from '@/services/platform'
import { errorText } from '@/features/platform/errorText'
import { LOGO_ACCEPT, checkLogo } from '@/features/platform/logoFile'
import { useSquare } from './squareContext'

// The square's two logos on Settings (W10-R17; redesigned in W23-R38 from `Square Settings Redesign.html`): main logo and the one for dark backgrounds, side by
// side, each a card with a preview on a matching light or dark ground, a drop zone (click or drop a file) and Remove as a quiet text link.
// PNG, JPEG or WebP up to 1 MB (logoFile.ts); the API enforces the same.
const { t } = useI18n()
const { sq, set } = useSquare()
const logoBusy = ref(false)
const logoError = ref('')
const over = ref<'' | 'main' | 'dark'>('')
const mainInput = ref<HTMLInputElement>()
const darkInput = ref<HTMLInputElement>()
async function upload(file: File | undefined, variant?: 'dark') {
  if (!file || !sq.value) return
  const problem = checkLogo(file)
  if (problem) { logoError.value = t(problem === 'type' ? 'plat.create.logoType' : 'plat.create.logoSize'); return }
  logoError.value = ''
  logoBusy.value = true
  try { set(await platform.uploadSquareLogo(sq.value.id, file, variant)) } catch (e) { logoError.value = errorText(t, e) } finally { logoBusy.value = false }
}
async function choose(ev: Event, variant?: 'dark') {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  await upload(file, variant)
}
async function drop(ev: DragEvent, variant?: 'dark') {
  over.value = ''
  await upload(ev.dataTransfer?.files?.[0], variant)
}
async function remove(variant?: 'dark') {
  if (!sq.value) return
  logoBusy.value = true
  try { set(await platform.removeSquareLogo(sq.value.id, variant)) } catch (e) { logoError.value = errorText(t, e) } finally { logoBusy.value = false }
}
</script>

<template>
  <section v-if="sq" class="sl">
    <h2 class="bs-h2 sl-h">{{ t('portal.theme.logoTitle') }}</h2>
    <p class="sl-sub">{{ t('squareSettings.logoSub') }}</p>
    <div class="sl-grid">
      <div class="sl-card">
        <div><h3>{{ t('portal.theme.mainTitle') }}</h3><p>{{ t('squareSettings.mainSub') }}</p></div>
        <div class="sl-row">
          <div class="sl-pv"><img v-if="sq.logo_url" :src="sq.logo_url" alt=""><span v-else>{{ t('portal.theme.noLogo') }}</span></div>
          <div class="sl-side">
            <label class="sl-dz" :class="over === 'main' && 'sl-on'" @dragover.prevent="over = 'main'" @dragenter.prevent="over = 'main'" @dragleave="over = ''" @drop.prevent="drop($event)">
              <span class="sl-dz__t"><b>{{ sq.logo_url ? t('portal.theme.replaceLogo') : t('portal.theme.addLogo') }}</b><small>{{ t('portal.theme.mainHint') }}</small></span>
              <AppButton icon="upload" class="sl-btn" variant="secondary" size="sm" :loading="logoBusy" @click.prevent="mainInput?.click()">{{ t('portal.theme.chooseFile') }}</AppButton>
              <input ref="mainInput" type="file" :accept="LOGO_ACCEPT" hidden @change="choose($event)">
            </label>
            <button v-if="sq.logo_url" type="button" class="sl-rm" :disabled="logoBusy" @click="remove()"><AppIcon name="trash" :size="12" />{{ t('portal.theme.removeLogo') }}</button>
          </div>
        </div>
      </div>
      <div class="sl-card">
        <div><h3>{{ t('portal.theme.darkTitle') }}</h3><p>{{ t('squareSettings.darkSub') }}</p></div>
        <div class="sl-row">
          <div class="sl-pv sl-pv--d"><img v-if="sq.logo_dark_url" :src="sq.logo_dark_url" alt=""><span v-else>{{ t('portal.theme.noLogo') }}</span></div>
          <div class="sl-side">
            <label class="sl-dz" :class="over === 'dark' && 'sl-on'" @dragover.prevent="over = 'dark'" @dragenter.prevent="over = 'dark'" @dragleave="over = ''" @drop.prevent="drop($event, 'dark')">
              <span class="sl-dz__t"><b>{{ sq.logo_dark_url ? t('portal.theme.replaceLogo') : t('portal.theme.addLogo') }}</b><small>{{ t('portal.theme.darkHint') }}</small></span>
              <AppButton icon="upload" class="sl-btn" variant="secondary" size="sm" :loading="logoBusy" @click.prevent="darkInput?.click()">{{ t('portal.theme.chooseFile') }}</AppButton>
              <input ref="darkInput" type="file" :accept="LOGO_ACCEPT" hidden @change="choose($event, 'dark')">
            </label>
            <button v-if="sq.logo_dark_url" type="button" class="sl-rm" :disabled="logoBusy" @click="remove('dark')"><AppIcon name="trash" :size="12" />{{ t('portal.theme.removeLogo') }}</button>
          </div>
        </div>
      </div>
    </div>
    <AppAlert v-if="logoError" tone="danger" style="margin-top: 14px">{{ logoError }}</AppAlert>
  </section>
</template>

<style scoped>
.sl-h { font-size: 28px; margin: 34px 0 4px; }
.sl-sub { margin: 0 0 14px; color: var(--color-text-muted); font-size: var(--text-sm); }
.sl-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.sl-card { display: grid; gap: 14px; align-content: start; padding: 18px 20px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--shape-surface); }
.sl-card h3 { margin: 0; font: 600 15px var(--font-sans); }
.sl-card p { margin: 2px 0 0; color: var(--color-text-muted); font-size: var(--text-sm); }
.sl-row { display: grid; grid-template-columns: 132px minmax(0, 1fr); gap: 14px; align-items: stretch; }
.sl-side { display: grid; gap: 10px; align-content: space-between; min-width: 0; }
.sl-pv { display: grid; place-items: center; width: 132px; height: 132px; overflow: hidden; padding: 8px; border: 1px solid var(--color-border); border-radius: var(--shape-inner); background: repeating-linear-gradient(45deg, var(--color-surface) 0 10px, var(--color-surface-sunken) 10px 20px); color: var(--color-text-muted); font: 11px var(--font-mono); text-align: center; }
.sl-pv--d { background: repeating-linear-gradient(45deg, #2a211b 0 10px, #241c17 10px 20px); border-color: #2a211b; color: #b9a999; }
.sl-pv img { width: 100%; height: 100%; object-fit: contain; }
.sl-dz { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding: 14px; border: 1.5px dashed var(--color-border-strong); border-radius: var(--shape-inner); cursor: pointer; }
.sl-dz:hover, .sl-on { border-color: var(--color-brass); background: var(--color-brass-subtle); }
.sl-dz__t { display: grid; gap: 2px; min-width: 0; flex: 1 1 200px; }
.sl-dz__t b { font-size: var(--text-sm); }
.sl-dz__t small { color: var(--color-text-muted); font-size: var(--text-xs); }
.sl-btn.sl-btn { padding: 0 12px; border-radius: var(--shape-control); border-color: var(--color-border); background: var(--color-surface); color: var(--color-text); font: 600 10px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; white-space: nowrap; }
.sl-btn.sl-btn:hover { border-color: var(--color-brass); background: var(--color-surface-sunken); }
.sl-rm { justify-self: start; padding: 0; border: 0; background: none; color: var(--color-text-muted); font: 600 10px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
.sl-rm:hover { color: var(--color-brass-text); }
@media (max-width: 700px) { .sl-grid { grid-template-columns: 1fr; } }
@media (max-width: 460px) { .sl-row { grid-template-columns: 1fr; } .sl-pv { width: 100%; height: 120px; } }
</style>
