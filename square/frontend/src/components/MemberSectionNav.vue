<script setup lang="ts">
import SectionTabs from './SectionTabs.vue'
import { moduleEnabled } from '../services/modules'

// Shared by every page in the admin Members area, so the same actions are reachable from each one.
// While the Memberships module is off the area is a plain people list (ADR 044): 'People' and Duplicates only.
const membershipsOn = moduleEnabled('memberships')
const tabs = membershipsOn
  ? [
      // Everyone who has signed in, whether or not they hold a membership.
      { to: '/admin/members/users', label: 'Users' },
      { to: '/admin/members', label: 'Members' },
      { to: '/admin/members/follow-up', label: 'Awaiting payment' },
      { to: '/admin/members/duplicates', label: 'Duplicates' },
      { to: '/admin/membership-types', label: 'Membership types' },
      { to: '/admin/members/import', label: 'Import' },
      // The in-person signup flow runs in its own full-screen layout for volunteers at a table.
      { to: '/membership-drive', label: 'Membership drive' },
    ]
  : [
      { to: '/admin/members/users', label: 'Users' },
      { to: '/admin/members', label: 'People' },
      { to: '/admin/members/duplicates', label: 'Duplicates' },
    ]
</script>

<template>
  <SectionTabs :tabs="tabs" label="Members sections" class="member-section-nav" />
</template>
