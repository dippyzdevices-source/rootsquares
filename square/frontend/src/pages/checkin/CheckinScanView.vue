<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import BaseAvatar from '../../components/ui/BaseAvatar.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseSpinner from '../../components/ui/BaseSpinner.vue'
import { scanTicket, fetchCheckinSummary, type ScanResult, type CheckinSummary } from '../../services/checkinApi'
import { randomSpinnerVariant, type SpinnerVariant } from '../../utils/spinner'
import { createQrScanner, type QrScannerHandle, type CameraOption } from '../../utils/qrScanner'
import { formatEventDate, formatDateTime } from '../../utils/date'

const videoEl = ref<HTMLVideoElement | null>(null)
const manualCode = ref('')
const result = ref<ScanResult | null>(null)
const summary = ref<CheckinSummary | null>(null)
const cameraAvailable = ref(false)
const isSubmitting = ref(false)
// A fresh motif each scan, not a fixed one — the design system's "one motif per surface"
// guidance is about not showing two DIFFERENT motifs on screen at once, not about a single
// transient overlay staying the same every time it appears.
const spinnerVariant = ref<SpinnerVariant>(randomSpinnerVariant())
const cameras = ref<CameraOption[]>([])
const selectedCameraId = ref('')
const online = ref(navigator.onLine)

const cameraOptions = computed(() => [
  { value: '', label: 'Default camera' },
  ...cameras.value.map((camera) => ({ value: camera.id, label: camera.label })),
])

const progressPct = computed(() => {
  if (!summary.value || summary.value.total_tickets === 0) return 0
  return Math.round((summary.value.checked_in_count / summary.value.total_tickets) * 100)
})

const RESULT_COPY: Record<string, { tone: string; title: string; line: (r: ScanResult) => string }> = {
  valid: {
    tone: 'success',
    title: 'Admitted',
    line: (r) => `${r.customer_name ?? 'This ticket'} is checked in for ${r.event_title ?? 'this event'}.`,
  },
  already_used: {
    tone: 'danger',
    title: 'Already checked in',
    line: (r) => `${r.customer_name ?? 'This ticket'} was already checked in at ${r.checked_in_at ? formatDateTime(r.checked_in_at) : '—'}.`,
  },
  voided: {
    tone: 'danger',
    title: 'Ticket cancelled',
    line: () => 'This order was cancelled — the ticket is no longer valid for entry.',
  },
  not_assigned: {
    tone: 'warning',
    title: 'Not your event',
    line: (r) => `This ticket is for ${r.event_title ?? 'another event'} — you're not assigned to scan for it.`,
  },
  invalid: {
    tone: 'danger',
    title: 'Invalid ticket',
    line: () => 'No ticket matches this code.',
  },
  pre_event: {
    tone: 'warning',
    title: 'Not yet valid',
    line: (r) => `This ticket is valid on the event day (${r.event_start_date ? formatEventDate(r.event_start_date) : 'not yet'}) — it's too early to check in.`,
  },
  post_event: {
    tone: 'danger',
    title: 'Event has ended',
    line: (r) => `This event ended on ${r.event_end_date ? formatEventDate(r.event_end_date) : 'an earlier date'} — the ticket is no longer valid.`,
  },
  error: {
    tone: 'neutral',
    title: "Couldn't reach the server",
    line: () => 'Check your connection and try again.',
  },
}

// Outcomes carrying real ticket data — shown as a ticket-detail card so the volunteer
// always knows which ticket they're looking at, regardless of the outcome's tone.
const TICKET_CARD_RESULTS = new Set(['valid', 'already_used', 'pre_event', 'post_event', 'voided'])

const resultCopy = computed(() => (result.value ? RESULT_COPY[result.value.result] : null))
const showTicketCard = computed(() => !!result.value && TICKET_CARD_RESULTS.has(result.value.result))

let scanner: QrScannerHandle | null = null
let summaryInterval: ReturnType<typeof setInterval> | null = null

async function loadSummary() {
  try {
    summary.value = await fetchCheckinSummary()
  } catch {
    // Live count is a nice-to-have — don't block scanning if it fails to load.
  }
}

async function submitCode(code: string) {
  const trimmed = code.trim()
  if (!trimmed || result.value || isSubmitting.value) return
  spinnerVariant.value = randomSpinnerVariant()
  isSubmitting.value = true
  let scanResult: ScanResult
  try {
    scanResult = await scanTicket(trimmed)
  } catch {
    // A thrown request (network failure, expired token, 500, dropped connection) is NOT the
    // same as a genuinely invalid ticket code — don't turn away a paying guest because the
    // backend hiccuped. See the 'error' branch above.
    scanResult = { result: 'error' }
  } finally {
    isSubmitting.value = false
  }
  // Pause decoding while feedback is up — otherwise the camera keeps firing decode events for
  // the same still-framed code, which would immediately re-trigger submitCode with a
  // now-"used" ticket, showing a confusing false "already checked in" right after a successful
  // scan.
  scanner?.pause()
  manualCode.value = ''
  loadSummary()
  result.value = scanResult
}

function resumeScanning() {
  // Only if the camera actually came up in the first place — otherwise (manual-entry-only
  // mode) this would just re-throw the same camera error start() hit on mount, as an
  // unhandled rejection.
  if (cameraAvailable.value) {
    scanner?.start().catch(() => {
      // Resuming the camera can fail transiently (e.g. it was revoked) — manual entry still
      // works either way, so there's nothing more to do here.
    })
  }
}

function dismissResult() {
  // Resume before clearing the result so any decode firing during the (async) resume is still
  // guarded by submitCode's `if (result.value) return` check.
  resumeScanning()
  result.value = null
}

function handleOnline() {
  online.value = true
}

function handleOffline() {
  online.value = false
}

onMounted(async () => {
  loadSummary()
  summaryInterval = setInterval(loadSummary, 5000)

  window.addEventListener('online', handleOnline)
  window.addEventListener('offline', handleOffline)

  if (videoEl.value) {
    scanner = createQrScanner(videoEl.value, (code) => submitCode(code))
    try {
      await scanner.start()
      cameraAvailable.value = true
    } catch {
      cameraAvailable.value = false // camera unavailable — manual entry still works
    }

    if (cameraAvailable.value) {
      try {
        cameras.value = await scanner.listCameras()
      } catch {
        // Camera picker is a convenience — a laptop/browser that can't enumerate devices
        // just keeps using whatever camera qr-scanner already started with.
      }
    }
  }
})

watch(selectedCameraId, async (cameraId) => {
  if (!cameraId || !scanner) return
  try {
    await scanner.setCamera(cameraId)
  } catch {
    // Switching cameras can fail transiently (e.g. the device was unplugged) — the
    // previously active camera keeps running either way.
  }
})

onUnmounted(() => {
  scanner?.stop()
  if (summaryInterval) clearInterval(summaryInterval)
  window.removeEventListener('online', handleOnline)
  window.removeEventListener('offline', handleOffline)
})
</script>

<template>
  <div class="ds-scope ds-force-dark" style="max-width: 460px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--ds-space-4); padding: var(--ds-space-4) var(--ds-gutter) var(--ds-space-8)">
    <div class="ds-checkin-appbar">
      <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-3)">
        <div>
          <p class="ds-eyebrow" style="color: var(--ds-action-accent); font-size: 9px">Door check-in</p>
          <h1 class="ds-checkin-title">Scan tickets</h1>
        </div>
        <span class="ds-checkin-sync" :class="online ? 'ds-checkin-sync-online' : 'ds-checkin-sync-offline'">
          <svg v-if="online" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13a10 10 0 0 1 14 0" /><path d="M8.5 16.5a5 5 0 0 1 7 0" /><path d="M2 8.82a15 15 0 0 1 20 0" /><line x1="12" y1="20" x2="12.01" y2="20" /></svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="1" y1="1" x2="23" y2="23" /><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" /><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" /><path d="M10.71 5.05A16 16 0 0 1 22.58 9" /><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" /><path d="M8.53 16.11a6 6 0 0 1 6.95 0" /><line x1="12" y1="20" x2="12.01" y2="20" /></svg>
          {{ online ? 'Synced' : 'Offline' }}
        </span>
      </div>
      <div v-if="summary" style="display: flex; align-items: center; gap: var(--ds-space-3)">
        <div class="ds-progress-track" style="flex: 1"><div class="ds-progress-bar ds-progress-bar-accent" :style="{ width: `${progressPct}%` }"></div></div>
        <span class="ds-meta" style="white-space: nowrap">{{ summary.checked_in_count }} / {{ summary.total_tickets }} in</span>
      </div>
    </div>

    <div class="ds-scan-frame">
      <div class="ds-scan-frame-grain"></div>
      <video ref="videoEl" class="ds-scan-frame-video" muted playsinline></video>

      <div v-if="!cameraAvailable" class="ds-scan-overlay">
        <svg class="ds-scan-overlay-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><line x1="14" y1="14" x2="14" y2="21" /><line x1="21" y1="14" x2="21" y2="21" /><line x1="14" y1="17.5" x2="21" y2="17.5" /></svg>
        <p class="ds-scan-overlay-hint">Camera unavailable — use manual entry below</p>
      </div>
      <div v-else-if="isSubmitting" class="ds-scan-overlay">
        <BaseSpinner :variant="spinnerVariant" size="xl" tone="on-dark" label="Reading" />
        <p class="ds-scan-overlay-hint">Reading&hellip;</p>
      </div>
      <template v-else>
        <span class="ds-scan-corner ds-scan-corner-tl"></span>
        <span class="ds-scan-corner ds-scan-corner-tr"></span>
        <span class="ds-scan-corner ds-scan-corner-bl"></span>
        <span class="ds-scan-corner ds-scan-corner-br"></span>
        <span class="ds-scan-line"></span>
      </template>
    </div>

    <BaseSelect v-if="cameraAvailable && cameras.length > 1" v-model="selectedCameraId" :options="cameraOptions" />

    <div style="display: flex; gap: var(--ds-space-2); align-items: center">
      <label class="ds-field-control" style="flex: 1">
        <span class="ds-field-prefix">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg>
        </span>
        <input v-model="manualCode" type="text" placeholder="Enter code manually" class="ds-field-input" @keyup.enter="submitCode(manualCode)" />
      </label>
      <BaseButton type="button" class="manual-checkin" @click="submitCode(manualCode)">
        Check in
      </BaseButton>
    </div>

    <div
      v-if="result && resultCopy"
      class="checkin-result-panel ds-checkin-result-overlay"
      @click="dismissResult"
    >
      <div class="ds-checkin-result-banner" :class="`ds-checkin-result-tone-${resultCopy.tone}`">
        <span class="ds-checkin-result-icon">
          <svg v-if="resultCopy.tone === 'success'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
          <svg v-else-if="resultCopy.tone === 'danger'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          <svg v-else-if="resultCopy.tone === 'warning'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="1" y1="1" x2="23" y2="23" /><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" /><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" /><path d="M10.71 5.05A16 16 0 0 1 22.58 9" /><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" /><line x1="12" y1="20" x2="12.01" y2="20" /></svg>
        </span>
        <div>
          <p class="ds-checkin-result-title">{{ resultCopy.title }}</p>
          <p class="ds-checkin-result-line">{{ resultCopy.line(result) }}</p>
          <div v-if="result.result === 'already_used'" class="ds-checkin-scanned-by" style="margin-top: var(--ds-space-3)">
            <p class="ds-caption" style="margin: 0 0 6px">Checked in by</p>
            <div style="display: flex; align-items: center; gap: var(--ds-space-3)">
              <BaseAvatar :name="result.checked_in_by_name ?? result.checked_in_by" size="sm" />
              <span>
                {{ result.checked_in_by_name ?? result.checked_in_by ?? 'Someone else' }}
                <div v-if="result.checked_in_by_name" class="ds-caption">{{ result.checked_in_by }}</div>
              </span>
            </div>
          </div>
        </div>
      </div>
      <div v-if="showTicketCard" class="ds-checkin-ticket-card">
        <div class="ds-checkin-ticket-head">
          <div>
            <p class="ds-checkin-ticket-name">{{ result.customer_name }}</p>
            <p class="ds-checkin-ticket-meta">{{ result.ticket_type }}<template v-if="result.event_title"> &middot; {{ result.event_title }}</template></p>
          </div>
        </div>
      </div>
      <p class="ds-checkin-hint">Tap to continue scanning</p>
    </div>
  </div>
</template>
