import { ref } from 'vue'

export type ToastTone = 'success' | 'info' | 'warning' | 'danger'
export interface ToastAction { label: string; run: () => void }
export interface Toast { id: number; title: string; body?: string; tone: ToastTone; persist: boolean; action?: ToastAction; countdown: boolean }

// Shared by every area, so it lives at module level. Design v4 (export/screens.md "Toasts and snackbars"): success, info, warning and undo close by
// themselves after 6 seconds; an error (danger) stays until it is dismissed; at most 3 are shown (the oldest goes first); pointer or focus
// over a toast pauses its timer.
export const TOAST_MS = 6000
export const TOAST_MAX = 3
const toasts = ref<Toast[]>([])
const timers = new Map<number, { handle: number | undefined; started: number; left: number }>()
let nextId = 1

function clearTimer(id: number) {
  const t = timers.get(id)
  if (t?.handle !== undefined) window.clearTimeout(t.handle)
}
function dismiss(id: number) {
  clearTimer(id)
  timers.delete(id)
  toasts.value = toasts.value.filter((t) => t.id !== id)
}
function arm(id: number, ms: number) {
  clearTimer(id)
  timers.set(id, { handle: window.setTimeout(() => dismiss(id), ms), started: Date.now(), left: ms })
}
function pause(id: number) {
  const t = timers.get(id)
  if (!t || t.handle === undefined) return
  window.clearTimeout(t.handle)
  timers.set(id, { handle: undefined, started: 0, left: Math.max(1000, t.left - (Date.now() - t.started)) })
}
function resume(id: number) {
  const t = timers.get(id)
  if (t && t.handle === undefined) arm(id, t.left)
}

export function useToast() {
  /** Show a toast. `ms` overrides the 6 s (a number as 4th argument, as before); an error never closes by itself. */
  const push = (title: string, tone: ToastTone = 'success', body?: string, ms: number = TOAST_MS) => {
    add({ title, body, tone, persist: tone === 'danger', countdown: false }, ms)
  }
  /** Snackbar with an Undo action and the 6 s countdown line. */
  const pushUndo = (title: string, undo: () => void, undoLabel = 'Undo') => {
    add({ title, tone: 'info', persist: false, countdown: true, action: { label: undoLabel, run: undo } }, TOAST_MS)
  }
  return { toasts, push, pushUndo, dismiss, pause, resume }
}

function add(t: Omit<Toast, 'id'>, ms: number) {
  const id = nextId++
  let list = [...toasts.value, { ...t, id }]
  while (list.length > TOAST_MAX) {
    const gone = list.shift()!
    clearTimer(gone.id)
    timers.delete(gone.id)
  }
  toasts.value = list
  if (!t.persist) arm(id, ms)
}
