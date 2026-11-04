<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import BaseAvatar from './BaseAvatar.vue'
import NavIcon, { type NavIconName } from './NavIcon.vue'

export interface AccountMenuItem {
  id: string
  label: string
  to?: string
  icon?: NavIconName
  count?: number
  tone?: 'danger'
  divider?: boolean
}

const props = withDefaults(
  defineProps<{
    name: string
    shortName: string
    email?: string | null
    avatarUrl?: string | null
    meta?: string | null
    items: AccountMenuItem[]
  }>(),
  { email: null, avatarUrl: null, meta: null },
)

const emit = defineEmits<{ select: [id: string] }>()

const open = ref(false)
const rootEl = ref<HTMLElement | null>(null)
const route = useRoute()

const rows = computed(() => props.items)

function toggle() {
  open.value = !open.value
}

function close() {
  open.value = false
}

function pick(item: AccountMenuItem) {
  close()
  emit('select', item.id)
}

function handleClickOutside(event: MouseEvent) {
  if (open.value && rootEl.value && !rootEl.value.contains(event.target as Node)) {
    close()
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') close()
}

watch(
  () => route.fullPath,
  () => close(),
)

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div ref="rootEl" class="ds-account-menu">
    <button
      type="button"
      class="ds-account-menu-trigger"
      :class="{ 'ds-account-menu-trigger-open': open }"
      aria-haspopup="menu"
      :aria-expanded="open"
      @click="toggle"
    >
      <BaseAvatar :src="avatarUrl" :name="shortName" size="sm" />
      <span class="ds-account-menu-text">
        <span class="ds-account-menu-name">{{ shortName }}</span>
        <span v-if="meta" class="ds-account-menu-meta">{{ meta }}</span>
      </span>
      <svg
        class="ds-account-menu-caret"
        :class="{ 'ds-account-menu-caret-open': open }"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="m6 9 6 6 6-6" />
      </svg>
    </button>

    <div v-if="open" role="menu" class="ds-account-menu-panel">
      <div class="ds-account-menu-header">
        <p class="ds-account-menu-header-name">{{ name }}</p>
        <p v-if="email" class="ds-account-menu-header-email">{{ email }}</p>
        <p v-if="meta" class="ds-account-menu-header-meta">{{ meta }}</p>
      </div>
      <div class="ds-account-menu-items">
        <template v-for="(item, index) in rows" :key="item.id ?? `divider-${index}`">
          <span v-if="item.divider" class="ds-account-menu-divider" />
          <component
            :is="item.to ? 'router-link' : 'button'"
            v-else
            :type="item.to ? undefined : 'button'"
            :to="item.to"
            role="menuitem"
            class="ds-account-menu-row"
            :class="{ 'ds-account-menu-row-danger': item.tone === 'danger' }"
            @click="pick(item)"
          >
            <NavIcon v-if="item.icon" :name="item.icon" class="ds-account-menu-row-icon" />
            <span class="ds-account-menu-row-label">{{ item.label }}</span>
            <span v-if="item.count != null" class="ds-account-menu-row-count">{{ item.count }}</span>
          </component>
        </template>
      </div>
    </div>
  </div>
</template>
