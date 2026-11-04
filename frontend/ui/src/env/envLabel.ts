import { ref } from 'vue'

// The word of the environment strip (W26-R25), DISPLAY ONLY: "Staging", "Local" or empty. The server says it in its answer to the start-up status request
// (see gate/gate.ts), the application's main.ts stores it here before anything is mounted, and the strip reads it. No code behaves differently because of it.
export const envLabel = ref('')
export function setEnvLabel(value: string | undefined | null): void {
  envLabel.value = typeof value === 'string' ? value.trim() : ''
}
