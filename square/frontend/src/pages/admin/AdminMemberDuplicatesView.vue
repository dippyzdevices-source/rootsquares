<script setup lang="ts">
import { ref, onMounted } from 'vue'
import BaseAvatar from '../../components/ui/BaseAvatar.vue'
import MemberSectionNav from '../../components/MemberSectionNav.vue'
import { moduleEnabled } from '../../services/modules'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import {
  fetchDuplicateMembers,
  mergeAdminMember,
  type DuplicateGroup,
  type AdminMemberSummary,
} from '../../services/adminMembersApi'
import { humanize } from '../../utils/formatEnum'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const { label: membershipStatusLabel } = useLookup('membership_status')
// Without the Memberships module (ADR 044) this is a list of people and nothing is said about memberships.
const membershipsOn = moduleEnabled('memberships')
const toast = useToast()

const groups = ref<DuplicateGroup[]>([])
const loading = ref(true)
const error = ref(false)
const merging = ref(false)
const confirmOpen = ref(false)
const pending = ref<{ keep: AdminMemberSummary; others: AdminMemberSummary[] } | null>(null)

async function load() {
  loading.value = true
  error.value = false
  try {
    groups.value = (await fetchDuplicateMembers()).groups
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function askMerge(group: DuplicateGroup, keep: AdminMemberSummary) {
  pending.value = { keep, others: group.members.filter((m) => m.id !== keep.id) }
  confirmOpen.value = true
}

async function confirmMerge() {
  if (!pending.value) return
  merging.value = true
  try {
    for (const other of pending.value.others) {
      await mergeAdminMember(pending.value.keep.id, other.id)
    }
    toast.success('Members merged')
    confirmOpen.value = false
    await load()
  } catch (err) {
    toast.error(err instanceof Error ? err.message : 'Could not merge these members')
    confirmOpen.value = false
    await load()
  } finally {
    merging.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">{{ membershipsOn ? 'Duplicate members' : 'Duplicate people' }}</h1>
      </div>
    </div>

    <MemberSectionNav />

    <p class="ds-meta">
      Records that share an email, or the same name and phone. Choose the one to keep — {{ membershipsOn ? 'memberships, ' : '' }}
      family entries and tasks from the other record move onto it, and the other record is deleted.
    </p>

    <BaseLoadingState v-if="loading" label="Looking for duplicates…" />
    <div v-else-if="error" class="ds-alert ds-alert-danger"><div>Could not load duplicates.</div></div>
    <div v-else-if="groups.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
      <p class="ds-meta">No duplicates found.</p>
    </div>

    <template v-else>
      <section v-for="(group, i) in groups" :key="i" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <span class="ds-badge ds-badge-neutral" style="align-self: flex-start">
          {{ group.reason === 'email' ? 'Same email' : 'Same name and phone' }}
        </span>
        <div
          v-for="member in group.members"
          :key="member.id"
          style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-3); flex-wrap: wrap"
        >
          <span style="display: inline-flex; align-items: center; gap: var(--ds-space-3); min-width: 0">
            <BaseAvatar :name="member.name" size="sm" />
            <span style="min-width: 0">
              <router-link :to="`/admin/members/${member.id}`" style="color: var(--ds-text-primary); font-weight: 500">{{ member.name }}</router-link>
              <div class="ds-caption" style="overflow-wrap: anywhere">
                {{ member.email || 'No email' }}<template v-if="member.phone"> · {{ member.phone }}</template>
                <template v-if="member.latest_membership"> · {{ humanize(member.latest_membership.membership_type) }} {{ membershipStatusLabel(member.latest_membership.status) }}</template>
                <template v-if="member.linked"> · Has login</template>
              </div>
            </span>
          </span>
          <BaseButton type="button" variant="secondary" size="sm" class="keep-member" @click="askMerge(group, member)">
            Keep this one
          </BaseButton>
        </div>
      </section>
    </template>

    <BaseModal v-model="confirmOpen" title="Merge members?">
      <div v-if="pending" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <p class="ds-body">
          Keep <strong>{{ pending.keep.name }}</strong> and merge
          {{ pending.others.map((o) => o.name).join(', ') }} into it. The other
          {{ pending.others.length === 1 ? 'record' : 'records' }} will be deleted. This can't be undone.
        </p>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" size="md" @click="confirmOpen = false">Cancel</BaseButton>
          <BaseButton type="button" variant="primary" size="md" class="confirm-merge" :disabled="merging" @click="confirmMerge">
            {{ merging ? 'Merging…' : 'Merge' }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>
  </div>
</template>
