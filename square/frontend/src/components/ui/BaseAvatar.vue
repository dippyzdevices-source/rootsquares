<script setup lang="ts">
withDefaults(
  defineProps<{
    src?: string | null
    name?: string | null
    size?: 'sm' | 'md' | 'lg' | 'xl'
  }>(),
  { src: null, name: null, size: 'md' },
)

function initials(name?: string | null): string {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  const first = parts[0]?.[0] ?? ''
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : ''
  return (first + last).toUpperCase() || '?'
}

const sizeClasses: Record<'sm' | 'md' | 'lg' | 'xl', string> = {
  sm: 'h-6 w-6 text-xs',
  md: 'h-10 w-10 text-sm',
  lg: 'h-16 w-16 text-lg',
  xl: 'h-24 w-24 text-2xl',
}
</script>

<template>
  <img
    v-if="src"
    :src="src"
    :alt="name ?? 'Profile picture'"
    class="shrink-0 rounded-full object-cover"
    :class="sizeClasses[size]"
  />
  <div
    v-else
    class="flex shrink-0 items-center justify-center rounded-full bg-primary/20 font-medium text-primary"
    :class="sizeClasses[size]"
  >
    {{ initials(name) }}
  </div>
</template>
