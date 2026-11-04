<script setup lang="ts">
import BaseAvatar from './BaseAvatar.vue'

withDefaults(
  defineProps<{
    name?: string | null
    email?: string | null
    avatarUrl?: string | null
    size?: 'sm' | 'md' | 'lg' | 'xl'
  }>(),
  { name: null, email: null, avatarUrl: null, size: 'sm' },
)
</script>

<template>
  <div class="ds-avatar-label">
    <BaseAvatar :src="avatarUrl" :name="name" :size="size" />
    <div class="ds-avatar-label-text">
      <span class="ds-avatar-label-name">{{ name ?? email ?? 'Unknown' }}</span>
      <span v-if="name && email" class="ds-avatar-label-email">{{ email }}</span>
      <!-- Extra lines under the email (e.g. a phone number), aligned with the name. -->
      <slot />
    </div>
  </div>
</template>
