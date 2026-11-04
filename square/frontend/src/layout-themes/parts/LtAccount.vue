<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { moduleEnabled } from '../../services/modules'
import { useAuthStore } from '../../stores/auth'
import LtAccountMenu from './LtAccountMenu.vue'

// Sign-in and account area of the themed shells (W9-R5). In headers (`menu`, the default) it is the default header's: Login for a visitor, the account menu
// (avatar and name; portal, tickets, family, payments, settings, Admin console, Check-in, Sign out) for someone signed in, and with `short` the Contact link
// of the utility bar first (W10-R6). Without `menu` (the footer) it is the plain text links.
withDefaults(defineProps<{ short?: boolean; menu?: boolean }>(), { menu: true })
const auth = useAuthStore()
const router = useRouter()
const adminLink = computed(() => auth.isAdmin)
async function signOut() {
  await auth.signOut()
  router.push('/')
}
</script>

<template>
  <span v-if="menu" class="lt-account">
    <router-link v-if="short" to="/contact" class="lt-acct-contact">Contact</router-link>
    <LtAccountMenu :join="false" />
  </span>
  <span v-else class="lt-account">
    <template v-if="!auth.isAuthenticated"><router-link to="/login">Sign in</router-link></template>
    <template v-else>
      <router-link to="/member">My portal</router-link>
      <router-link v-if="adminLink" to="/admin">Admin</router-link>
      <router-link v-if="(adminLink || auth.isVolunteer) && moduleEnabled('checkin')" to="/checkin">Check-in</router-link>
      <button type="button" @click="signOut">Sign out</button>
    </template>
  </span>
</template>
