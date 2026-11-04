<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { squareProfile } from '../../services/squareConfig'
import { fetchSettings, type SiteSettings } from '../../services/settingsApi'

// A legal page the square has not published yet (rootsquares W6-R41). bca-oslo's own Terms of Sale and Privacy Policy named its legal entity,
// organisation number, address and Norwegian law, so they cannot stand in for another association: the square shows who to ask instead.
// The square's own text (Admin, Settings, Legal texts; W6-R51) is shown when it has one.
const props = defineProps<{ title: string; what: string; field: 'privacy_text' | 'terms_text' }>()

const settings = ref<SiteSettings | null>(null)
const text = computed(() => (settings.value?.[props.field] ?? '').trim())
onMounted(async () => {
  try {
    settings.value = await fetchSettings()
  } catch {
    settings.value = null // the page still says who it is and that the text is missing
  }
})
</script>

<template>
  <div class="ds-scope">
    <section class="ds-band ds-band-wash">
      <div class="ds-container">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Legal</span>
          <h1 class="ds-display ds-display-m">{{ title }}</h1>
        </div>
      </div>
    </section>

    <section class="ds-band ds-band-paper">
      <div class="ds-container ds-body-l" style="max-width: var(--ds-container-narrow); margin: 0 auto">
        <div v-if="text" data-testid="legal-text" style="white-space: pre-wrap">{{ text }}</div>
        <template v-else>
        <p>{{ squareProfile.name }} has not published its {{ what }} on this website yet.</p>
        <p>If you have a question about {{ what === 'privacy policy' ? 'your personal data' : 'a purchase' }}, please contact us:</p>
        <div class="ds-card">
          <p><strong>{{ squareProfile.name }}</strong></p>
          <p v-if="settings?.contact_email">Email: <a :href="`mailto:${settings.contact_email}`">{{ settings.contact_email }}</a></p>
          <p v-if="settings?.contact_phone">Telephone: {{ settings.contact_phone }}</p>
          <p v-if="settings?.contact_address">Address: {{ settings.contact_address }}</p>
        </div>
        </template>
      </div>
    </section>
  </div>
</template>
