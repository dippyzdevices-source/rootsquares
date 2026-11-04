<script setup lang="ts">
import { computed } from 'vue'

// Mirrors the design system's own components/core/IconButton.jsx (outline/solid/bare variants,
// sm/md/lg sizes) — the reference itself is always a <button> since its mockup navigates via a
// JS callback, but real routes need a real link, so `to`/`href` are added here the same way
// BaseButton.vue supports them: three explicit branches rather than one dynamic <component
// :is>, since an unconditional :href fallthrough silently clobbers router-link's own
// internally-computed href (see BaseButton.vue's comment for the full explanation).
const props = withDefaults(
  defineProps<{
    label: string
    variant?: 'outline' | 'solid' | 'bare' | 'success' | 'warning' | 'danger' | 'info' | 'primary' | 'secondary'
    size?: 'sm' | 'md' | 'lg'
    to?: string | Record<string, unknown>
    href?: string
    disabled?: boolean
  }>(),
  { variant: 'outline', size: 'md', to: undefined, href: undefined, disabled: false },
)

const ICON_VARIANT: Record<string, string> = { primary: 'solid', secondary: 'outline' }
for (const v of ['outline', 'solid', 'bare', 'success', 'warning', 'danger', 'info']) ICON_VARIANT[v] = v

const classes = computed(() => [
  'ds-icon-btn',
  // Same aliases as the design system's IconButton: primary = solid, secondary = outline.
  ICON_VARIANT[props.variant] !== 'outline' ? `ds-icon-btn-${ICON_VARIANT[props.variant]}` : null,
  props.size !== 'md' ? `ds-icon-btn-${props.size}` : null,
])
</script>

<template>
  <router-link v-if="to" :to="to" :class="classes" :aria-label="label" :title="label" :aria-disabled="disabled" :tabindex="disabled ? -1 : undefined">
    <slot />
  </router-link>
  <a v-else-if="href" :href="href" :class="classes" :aria-label="label" :title="label" :aria-disabled="disabled" :tabindex="disabled ? -1 : undefined">
    <slot />
  </a>
  <button v-else type="button" :class="classes" :aria-label="label" :title="label" :disabled="disabled">
    <slot />
  </button>
</template>
