<script setup lang="ts">
import { ref, onMounted } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { downloadEventExport, fetchEventPass, type EventPassSummary } from '../../services/adminEventPassApi'
import { downloadBlob } from '../../utils/download'
import { formatEventDate } from '../../utils/date'
import { useToast } from '../../composables/useToast'

// The wrap-up of an Event pass (W11, ADR 044): when the event is over the owner downloads everything in one zip. The site is live for 45 days and then in a read-only
// archive for 45 days; at the end of the archive it is deleted, so this page says plainly what is kept and when it ends.
const toast = useToast()
const summary = ref<EventPassSummary | null>(null)
const loading = ref(true)
const error = ref(false)
const downloading = ref(false)

async function load() {
  try {
    summary.value = await fetchEventPass()
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

async function download() {
  downloading.value = true
  try {
    downloadBlob(await downloadEventExport(), 'event-export.zip')
    toast.success('Everything is downloaded. Keep the file safe.')
  } catch {
    toast.error('Could not download the export. Please try again.')
  } finally {
    downloading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Event wrap-up</h1>
      </div>
      <hr class="ds-section-line" />

      <BaseLoadingState v-if="loading" label="Loading…" />
      <BaseEmptyState v-else-if="error || !summary" title="Couldn't load the wrap-up" description="Please try again shortly." />
      <template v-else>
        <section class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <h2 class="ds-title">{{ summary.phase === 'archive' ? 'The event is over: this site is a read-only archive' : 'Your Event pass is live' }}</h2>
          <p class="ds-body" data-testid="event-pass-dates">
            <template v-if="summary.phase === 'archive'">
              Nothing can be bought or changed any more and only you can sign in. Download everything below. This site and all its data are
              <strong>deleted after {{ formatEventDate(summary.archive_until) }}</strong>.
            </template>
            <template v-else>
              The site is live until <strong>{{ formatEventDate(summary.live_until) }}</strong>. After that it becomes a read-only archive where only you can sign in, for 45
              more days, so you can save your reports. Then it is deleted.
            </template>
          </p>
        </section>

        <section class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
          <h2 class="ds-title">Download everything</h2>
          <p class="ds-meta">One zip file with:</p>
          <ul style="margin: 0; padding-inline-start: var(--ds-space-5); display: grid; gap: var(--ds-space-1)">
            <li v-for="line in summary.export" :key="line">{{ line }}</li>
          </ul>
          <div>
            <BaseButton type="button" class="download-export" :disabled="downloading" @click="download">
              {{ downloading ? 'Preparing the zip…' : 'Download everything (zip)' }}
            </BaseButton>
          </div>
          <p class="ds-meta">
            Keep the file. rootsquares keeps no copy once the site is deleted. The accounting report is a record and an export, not bookkeeping software: you, the organiser, are
            responsible for keeping your accounting records for as long as the law of your country requires. When you have saved it, say so on rootsquares (your square's page, Event pass).
          </p>
        </section>
      </template>
    </div>
  </div>
</template>
