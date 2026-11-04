<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import TButton from './TButton.vue'

// Cookie notice (design "Cookie notice"): sticky bottom card, Accept and Decline with equal weight. The choice is kept for the browser session (demo).
const KEY = 'rs-site-cookie'
const { t } = useI18n()
const read = () => { try { return sessionStorage.getItem(KEY) } catch { return null } }
const choice = ref<string | null>(read())
function pick(v: 'accepted' | 'declined') {
  choice.value = v
  try { sessionStorage.setItem(KEY, v) } catch { /* storage unavailable: asked again after a reload */ }
}
</script>

<template>
  <div v-if="!choice" class="t-cookie" role="dialog" :aria-label="t('site.cookie.title')">
    <div class="t-cookie__card">
      <div class="t-cookie__text"><b>{{ t('site.cookie.title') }}</b><div>{{ t('site.cookie.text') }}</div></div>
      <div class="t-row">
        <TButton variant="outline" @click="pick('declined')">{{ t('site.cookie.decline') }}</TButton>
        <TButton variant="outline" @click="pick('accepted')">{{ t('site.cookie.accept') }}</TButton>
      </div>
    </div>
  </div>
</template>
