import { reactive } from 'vue'

export type ToastVariant = 'info' | 'success' | 'error'

interface Toast {
  id: number
  message: string
  variant: ToastVariant
}

let nextId = 0
const toasts = reactive<Toast[]>([])

function show(message: string, variant: ToastVariant = 'info', duration = 4000) {
  const id = nextId++
  toasts.push({ id, message, variant })
  setTimeout(() => dismiss(id), duration)
}

function dismiss(id: number) {
  const index = toasts.findIndex((toast) => toast.id === id)
  if (index !== -1) toasts.splice(index, 1)
}

export function useToast() {
  return {
    toasts,
    success: (message: string, duration?: number) => show(message, 'success', duration),
    error: (message: string, duration?: number) => show(message, 'error', duration),
    info: (message: string, duration?: number) => show(message, 'info', duration),
    dismiss,
  }
}
