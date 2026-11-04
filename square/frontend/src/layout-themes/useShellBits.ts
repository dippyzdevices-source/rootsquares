// Small behaviours shared by the shells (rootsquares W9-R5): which nav item is current, and a menu that closes on Escape and on navigation and keeps
// the keyboard inside while it is a full-screen overlay.
import { nextTick, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { useRoute } from 'vue-router'

export function useActive() {
  const route = useRoute()
  const isActive = (to: string) => (to === '/' ? route.path === '/' : route.path === to || route.path.startsWith(`${to}/`))
  return { route, isActive }
}

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function useMenu(panel?: Ref<HTMLElement | null>, trap = false) {
  const open = ref(false)
  const route = useRoute()
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      open.value = false
      return
    }
    if (trap && e.key === 'Tab' && panel?.value) {
      const items = [...panel.value.querySelectorAll<HTMLElement>(FOCUSABLE)]
      if (!items.length) return
      const first = items[0]!
      const last = items[items.length - 1]!
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
  }
  watch(open, async (isOpen) => {
    if (isOpen) {
      document.addEventListener('keydown', onKey)
      if (trap) {
        await nextTick()
        panel?.value?.querySelector<HTMLElement>(FOCUSABLE)?.focus()
      }
    } else {
      document.removeEventListener('keydown', onKey)
    }
  })
  watch(() => route.fullPath, () => (open.value = false))
  onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
  return { open, toggle: () => (open.value = !open.value), close: () => (open.value = false) }
}

/** The clip-path of a torn paper edge: a ragged line along the bottom, `h` pixels per step of unevenness (prototype torn()). */
export function tornPolygon(h: number): string {
  const p = [0, 6, 2, 9, 4, 12, 3, 8, 1, 10]
  const points = Array.from({ length: 41 }, (_, i) => `${100 - i * 2.5}% calc(100% - ${p[i % 10]! * h}px)`)
  return `polygon(0 0,100% 0,${points.join(',')})`
}
