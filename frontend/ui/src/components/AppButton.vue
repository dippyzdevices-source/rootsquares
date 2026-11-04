<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, type RouteLocationRaw } from 'vue-router'
import AppIcon from './AppIcon.vue'

// Mirrors design/components/core/Button.jsx (.rs-btn)
const props = withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  block?: boolean
  icon?: string
  iconOnly?: boolean
  loading?: boolean
  disabled?: boolean
  to?: RouteLocationRaw
  href?: string
  type?: 'button' | 'submit' | 'reset'
  label?: string
  /** open the link in a new tab */
  external?: boolean
}>(), { variant: 'primary', size: 'md', type: 'button' })

const classes = computed(() => [
  'rs-btn',
  props.variant !== 'primary' && `rs-btn--${props.variant}`,
  props.size !== 'md' && `rs-btn--${props.size}`,
  props.block && 'rs-btn--block',
  props.iconOnly && 'rs-btn--icon',
])
</script>

<template>
  <RouterLink v-if="to && !disabled" :to="to" :class="classes" :aria-label="label"><AppIcon v-if="icon" :name="icon" /><slot /></RouterLink>
  <a v-else-if="href && !disabled" :href="href" :class="classes" :aria-label="label" :target="external ? '_blank' : undefined" :rel="external ? 'noopener noreferrer' : undefined"><AppIcon v-if="icon" :name="icon" /><slot /></a>
  <button v-else :type="type" :class="classes" :disabled="disabled" :aria-busy="loading || undefined" :aria-label="label">
    <AppIcon v-if="loading" name="loader" class="rs-spin" />
    <AppIcon v-else-if="icon" :name="icon" />
    <slot />
  </button>
</template>
