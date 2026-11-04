<script setup lang="ts">
import { squareProfile } from '../services/squareConfig'
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import BaseButton from '../components/ui/BaseButton.vue'
import ThemeToggle from '../components/ui/ThemeToggle.vue'

const auth = useAuthStore()
const router = useRouter()

// Volunteers have no admin section to return to — send them to the homepage instead, same
// convention as CheckinLayout.vue.
const homeLink = computed(() => (auth.isAdmin ? '/admin/members' : '/'))

async function handleLogout() {
  await auth.signOut()
  router.push('/')
}
</script>

<template>
  <div class="ds-scope" style="min-height: 100%; display: flex; flex-direction: column; background: var(--ds-surface-page)">
    <header style="border-bottom: 1px solid var(--ds-border-hairline)">
      <div class="ds-container" style="display: flex; align-items: center; justify-content: space-between; padding-top: var(--ds-space-3); padding-bottom: var(--ds-space-3)">
        <div style="display: flex; align-items: center; gap: var(--ds-space-4)">
          <router-link to="/membership-drive" style="display: flex; align-items: center; gap: var(--ds-space-2); text-decoration: none; color: var(--ds-text-heading); font-family: var(--ds-font-display); font-size: 17px">
            {{ squareProfile.name }} Membership Drive
          </router-link>
          <router-link :to="homeLink" class="ds-utility-link" style="color: var(--ds-text-muted); opacity: 1">&larr; Back</router-link>
        </div>
        <div style="display: flex; align-items: center; gap: var(--ds-space-3)">
          <ThemeToggle />
          <BaseButton type="button" variant="ghost" size="sm" @click="handleLogout">
            Logout
          </BaseButton>
        </div>
      </div>
    </header>
    <main style="flex: 1; width: 100%">
      <router-view />
    </main>
  </div>
</template>
