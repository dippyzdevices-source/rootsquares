<script setup lang="ts">
import { ref } from 'vue'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import CopyField from '@/components/ui/CopyField.vue'
import DataRow from '@rootsquares/ui/components/DataRow.vue'
import IconButton from '@/components/ui/IconButton.vue'
import KeyValue from '@/components/ui/KeyValue.vue'
import MeterBar from '@/components/ui/MeterBar.vue'
import RoleBadge from '@rootsquares/ui/components/RoleBadge.vue'
import SegToggle from '@/components/ui/SegToggle.vue'
import SwitchBtn from '@/components/ui/SwitchBtn.vue'
import TenantChip from '@/components/ui/TenantChip.vue'
import ToggleGroup from '@/components/ui/ToggleGroup.vue'
import UploadBox from '@/components/ui/UploadBox.vue'
import type { MenuItem } from '@rootsquares/ui/components/RowMenu.vue'

// Showcase of the platform v3 extension components (Brass Components.html: default, loading, empty, error). Developer page, not linked
// from the navigation, English only (see MISSING.md). Light/dark follows the header toggle.
const bio = ref('Ingrid has led the choir since 2019 and arranges the winter concert.')
const longBio = ref('x'.repeat(252))
const empty = ref('')
const sw = ref(true)
const sw2 = ref(false)
const scopes = ref<string[]>(['events'])
const mode = ref('light')
const device = ref('desktop')
const confirmOpen = ref(false)
const log = ref('')

const MEM: (MenuItem | '-')[] = [
  { id: 'edit', label: 'Edit', icon: 'edit' }, { id: 'up', label: 'Move up', icon: 'move-up' }, { id: 'down', label: 'Move down', icon: 'move-down' },
  { id: 'hide', label: 'Hide from public site', icon: 'eye' }, '-', { id: 'remove', label: 'Remove from committee', icon: 'trash', danger: true },
]
const name = 'Nordlys Cultural Society'
</script>

<template>
  <div class="mk-sec" style="gap: 28px">
    <header style="display: grid; gap: 8px">
      <span class="rs-eyebrow">Platform v3</span>
      <h1 class="bs-d" style="font-size: 40px">Extension components</h1>
      <p class="bs-lede" style="font-size: var(--text-base)">States as in Brass Components.html: default, loading, empty, error. Use the light/dark button in the header to check both modes.</p>
      <p v-if="log" class="bs-fine" role="status">Last action: {{ log }}</p>
    </header>

    <section class="bx-sec">
      <h2>Textarea</h2>
      <div class="bx-grid">
        <div><div class="bx-cap">Default</div><AppField v-model="bio" as="textarea" label="Short bio" hint="Shown on the public committee page." :max="240" /></div>
        <div><div class="bx-cap">Loading</div><AppField :model-value="''" as="textarea" label="Short bio" loading hint="" /></div>
        <div><div class="bx-cap">Empty</div><AppField v-model="empty" as="textarea" label="Short bio" placeholder="Write a short bio…" hint="Shown on the public committee page." :max="240" /></div>
        <div><div class="bx-cap">Error</div><AppField v-model="longBio" as="textarea" label="Short bio" error="Bio is too long. Shorten by 12 characters." :max="240" /></div>
      </div>
    </section>

    <section class="bx-sec">
      <h2>Alert</h2>
      <div style="display: grid; gap: 10px">
        <AppAlert tone="info" title="Verifying">We are checking your DNS records. This can take a few minutes.</AppAlert>
        <AppAlert tone="success" title="Domain is live">Your certificate is active.</AppAlert>
        <AppAlert tone="warning" title="DNS records pending">Add the records below at your registrar.<template #action><AppButton size="sm" variant="secondary" @click="log = 'Check now'">Check now</AppButton></template></AppAlert>
        <AppAlert tone="danger" title="Betalingen mislyktes">Kortet ble avvist. Prøv et annet kort eller kontakt banken din.</AppAlert>
        <AppAlert tone="warning" banner title="Past due">Your subscription is past due.</AppAlert>
      </div>
    </section>

    <section class="bx-sec">
      <h2>Copy field</h2>
      <div class="bx-grid">
        <div><div class="bx-cap">Default</div><CopyField label="CNAME value" value="nordlys.cname.rootsquares.app" /></div>
        <div><div class="bx-cap">Loading</div><CopyField label="CNAME value" state="loading" /></div>
        <div><div class="bx-cap">Empty</div><CopyField label="TXT value" state="empty" /></div>
        <div><div class="bx-cap">Error</div><CopyField label="Support access link" value="https://rootsquares.app/support/7f3a…" state="error" /></div>
      </div>
    </section>

    <section class="bx-sec">
      <h2>Upload</h2>
      <div class="bx-grid">
        <div><div class="bx-cap">File, empty</div><UploadBox /></div>
        <div><div class="bx-cap">File, uploading</div><UploadBox state="loading" name="Annual-report-2025.pdf" :progress="62" /></div>
        <div><div class="bx-cap">File, uploaded</div><UploadBox state="preview" name="Annual-report-2025.pdf" meta="412 KB · uploaded today" /></div>
        <div><div class="bx-cap">File, error</div><UploadBox state="error" error-text="Minutes.pdf is 8,4 MB. The limit is 5 MB." /></div>
        <div><div class="bx-cap">Portrait, empty</div><UploadBox kind="portrait" /></div>
        <div><div class="bx-cap">Portrait, preview</div><UploadBox kind="portrait" state="preview" name="ingrid.jpg" meta="1200 × 1500 · 640 KB" /></div>
      </div>
    </section>

    <section class="bx-sec">
      <h2>Data row, role badge, tenant chips</h2>
      <div class="bx-grid">
        <div>
          <div class="bx-cap">Rows</div>
          <div class="bx-list">
            <DataRow name="Ingrid Hansen" meta="Chair · visible" role="owner" :menu="MEM" @select="(id) => (log = `row menu: ${id}`)" />
            <DataRow name="Kjell-Magnus Sivertsen-Aarnes" meta="Nestleder og kommunikasjonsansvarlig · hidden" role="admin" :menu="MEM" />
            <DataRow loading />
          </div>
        </div>
        <div>
          <div class="bx-cap">Roles</div>
          <div class="bs-row" style="flex-wrap: wrap"><RoleBadge role="owner" /><RoleBadge role="admin" /><RoleBadge role="editor" /><RoleBadge role="viewer" /><RoleBadge role="support" /></div>
          <div class="bx-cap" style="margin-top: 16px">Tenant status</div>
          <div class="bs-row" style="flex-wrap: wrap"><TenantChip status="trial" /><TenantChip status="active" /><TenantChip status="pastDue" /><TenantChip status="suspended" /></div>
        </div>
      </div>
    </section>

    <section class="bx-sec">
      <h2>Switch, icon button, toggles</h2>
      <div class="bx-grid">
        <div>
          <div class="bx-cap">Switch</div>
          <div class="bs-row"><SwitchBtn v-model="sw" label="Visible on public site" /><span>Visible on public site</span></div>
          <div class="bs-row" style="margin-top: 8px"><SwitchBtn v-model="sw2" label="Events module" /><span>Events module</span></div>
        </div>
        <div>
          <div class="bx-cap">Icon buttons</div>
          <div class="bx-acts"><IconButton icon="move-up" label="Move up" /><IconButton icon="move-down" label="Move down" /><IconButton icon="eye" label="Hide from public site" :pressed="false" /><IconButton icon="edit" label="Edit" /><IconButton icon="trash" label="Remove" disabled /></div>
        </div>
        <div>
          <div class="bx-cap">Toggle group (multi)</div>
          <ToggleGroup v-model="scopes" label="Support access scope" :items="[{ value: 'events', label: 'Events', icon: 'calendar' }, { value: 'orders', label: 'Orders', icon: 'receipt' }, { value: 'committee', label: 'Committee', icon: 'users' }]" />
        </div>
        <div>
          <div class="bx-cap">Segmented (single)</div>
          <div style="display: grid; gap: 10px">
            <SegToggle v-model="mode" label="Preview mode" :items="[['light', 'Light'], ['dark', 'Dark']]" />
            <SegToggle v-model="device" label="Device" :items="[['phone', 'Phone'], ['tablet', 'Tablet'], ['desktop', 'Desktop']]" />
          </div>
        </div>
      </div>
    </section>

    <section class="bx-sec">
      <h2>Meter and key-value</h2>
      <div class="bx-grid">
        <div style="display: grid; gap: 12px">
          <MeterBar label="Members" value-text="86 / 200" :percent="43" />
          <MeterBar label="Storage" value-text="4,1 GB / 5 GB" :percent="82" />
        </div>
        <KeyValue :rows="[['Plan', 'Community'], ['Renews', '12 Nov 2026'], ['Address', 'nordlys.rootsquares.app']]" />
      </div>
    </section>

    <section class="bx-sec">
      <h2>Confirm dialog</h2>
      <div class="bx-scrim">
        <ConfirmDialog inline :name="name" title="Close organisation" body="Your site goes offline now. Members, orders and accounts are kept for 30 days, then deleted. You can reopen it until then." verb="Close organisation" />
      </div>
      <div><AppButton variant="secondary" @click="confirmOpen = true">Open as modal</AppButton></div>
      <ConfirmDialog v-if="confirmOpen" :name="name" title="Close organisation" body="Your site goes offline now. Members, orders and accounts are kept for 30 days, then deleted." verb="Close organisation" @cancel="confirmOpen = false" @confirm="confirmOpen = false; log = 'Close organisation confirmed (demo)'" />
    </section>
  </div>
</template>
