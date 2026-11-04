<script setup lang="ts">
// Members -> Users: everyone who has signed in, kept apart from the member roster. A sign-in account
// (User) is created the first time someone logs in with any role; it is only tied to a Member when the
// emails match, so this list can hold people who are not on the roster and the roster holds people who
// have never signed in.
import { onMounted, ref, watch } from 'vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseMultiSelect from '../../components/ui/BaseMultiSelect.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import MemberSectionNav from '../../components/MemberSectionNav.vue'
import { PAGE_SIZE } from '../../composables/useClientPagination'
import { useLookup } from '../../composables/useLookup'
import { useToast } from '../../composables/useToast'
import { fetchSignedInUsers, resendWelcomeEmail, type SignedInUser } from '../../services/adminUsersApi'
import { formatDateTime } from '../../utils/date'

const toast = useToast()
const { options: roleOptions, label: roleLabel } = useLookup('user_role')

const users = ref<SignedInUser[]>([])
const loading = ref(true)
const search = ref('')
const roles = ref<string[]>([])
const page = ref(1)
const totalPages = ref(1)
const total = ref(0)

// Filter/search changes go back to page 1 (the page watcher does the load when it moves).
function reload() {
  if (page.value !== 1) page.value = 1
  else void load()
}

async function load() {
  loading.value = true
  try {
    const data = await fetchSignedInUsers({ q: search.value || undefined, roles: roles.value, page: page.value, perPage: PAGE_SIZE })
    users.value = data.items
    totalPages.value = data.total_pages
    total.value = data.total
  } catch {
    toast.error('Could not load users')
  } finally {
    loading.value = false
  }
}

const sending = ref<number | null>(null)

// The automatic welcome email goes out once, at first sign-in - this sends it again after a failure.
async function resendWelcome(user: SignedInUser) {
  sending.value = user.id
  try {
    await resendWelcomeEmail(user.id)
    toast.success(`Welcome email sent to ${user.email}`)
  } catch {
    toast.error('Could not send the welcome email. Please try again shortly.')
  } finally {
    sending.value = null
  }
}

const roleTone = (role: string) => (role === 'admin' ? 'ds-badge-danger' : role === 'volunteer' ? 'ds-badge-success' : 'ds-badge-neutral')

watch(roles, reload)
watch(page, load)
onMounted(load)
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Members</h1>
      </div>

      <MemberSectionNav />

      <p class="ds-meta" style="max-width: 640px">
        Everyone who has signed in to the site, newest first. The Members tab lists only people who hold (or held) a membership;
        someone who just signed in and saved a profile shows up here, and their name opens their member page to give them one.
      </p>

      <div class="ds-toolbar">
        <BaseSearchField size="sm" class="ds-toolbar-search" v-model="search" placeholder="Search by name or email…" aria-label="Search by name or email" @keyup.enter="reload" />
        <BaseMultiSelect v-model="roles" size="sm" class="ds-toolbar-select" :options="roleOptions" all-label="All roles" aria-label="Filter by role" highlight-active />
      </div>

      <BaseLoadingState v-if="loading" label="Loading users…" />
      <BaseEmptyState
        v-else-if="users.length === 0"
        title="No users found"
        :description="search || roles.length ? 'No users match this filter or search.' : 'Nobody has signed in yet.'"
      />
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table users-log">
            <thead>
              <tr>
                <th>Email</th>
                <th>Profile</th>
                <th>Role</th>
                <th>Signed in with</th>
                <th>First sign-in</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in users" :key="user.id">
                <td data-emphasis>{{ user.email }}</td>
                <td>
                  <router-link v-if="user.member_id" :to="`/admin/members/${user.member_id}`" class="ds-ref-link">{{ user.member_name }}</router-link>
                  <span v-else class="ds-meta">Not on the member list</span>
                </td>
                <td><span class="ds-badge" :class="roleTone(user.role)">{{ roleLabel(user.role) }}</span></td>
                <td>{{ user.auth_provider === 'neon' ? 'Neon Auth' : user.auth_provider === 'supabase' ? 'Supabase' : user.auth_provider }}</td>
                <td>{{ user.first_sign_in ? formatDateTime(user.first_sign_in) : '—' }}</td>
                <td data-align="right">
                  <BaseIconButton variant="bare" size="sm" class="resend-welcome" :label="`Resend welcome email to ${user.email}`" :disabled="sending === user.id" @click="resendWelcome(user)">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2" /><path d="m22 7-10 6L2 7" /></svg>
                  </BaseIconButton>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <PaginationBar v-model:page="page" :total-pages="totalPages" :total="total" />
    </div>
  </div>
</template>
