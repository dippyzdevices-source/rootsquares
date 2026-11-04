<script setup lang="ts">
import { computed } from 'vue'

// Wraps the design system's own .ds-btn classes (design-system.css) rather than inventing a
// separate Tailwind-utility button style — those classes are already what every page uses
// directly (<button class="ds-btn ds-btn-primary">), so this component exists to give that
// same real button a single reusable, type-safe entry point instead of hand-copied class lists.
const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'accent' | 'accent-outline' | 'secondary' | 'ghost' | 'inverse' | 'paper' | 'success' | 'warning' | 'danger' | 'info'
    size?: 'sm' | 'md' | 'lg'
    type?: 'button' | 'submit' | 'reset'
    to?: string | Record<string, unknown>
    href?: string
    disabled?: boolean
    fullWidth?: boolean
  }>(),
  {
    variant: 'primary',
    size: 'md',
    type: 'button',
    to: undefined,
    href: undefined,
    disabled: false,
    fullWidth: false,
  },
)

const classes = computed(() => [
  'ds-btn',
  `ds-btn-${props.variant}`,
  `ds-btn-${props.size}`,
  { 'ds-btn-full': props.fullWidth },
])

// Three explicit template branches rather than one <component :is> — binding an unconditional
// :href on a dynamic RouterLink/a/button falls through and clobbers RouterLink's own
// internally-computed href (fallthrough attrs win over a component's own template attrs for
// anything but class/style), which silently dropped it. Kept as a comment here rather than in
// the template itself — a comment sibling before the v-if/else-if/else chain there turns this
// into a genuine multi-root fragment, which breaks Vue Test Utils' wrapper.element/classes().
//
// Uses the bare <router-link> tag (global resolution, matching every other page in this
// codebase) rather than `import { RouterLink } from 'vue-router'` — several existing spec
// files wholesale `vi.mock('vue-router', () => ({ useRoute: ... }))` with no RouterLink
// export, which breaks any component that imports RouterLink directly, even transitively.
// The bare tag resolves via Vue's component-name lookup (global registration or a test's
// `global.stubs`), never touching the mocked module namespace.
</script>

<template>
  <router-link v-if="to" :to="to" :class="classes" :aria-disabled="disabled" :tabindex="disabled ? -1 : undefined">
    <slot />
  </router-link>
  <a v-else-if="href" :href="href" :class="classes" :aria-disabled="disabled" :tabindex="disabled ? -1 : undefined">
    <slot />
  </a>
  <button v-else :type="type" :class="classes" :disabled="disabled">
    <slot />
  </button>
</template>
