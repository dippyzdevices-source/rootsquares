// Mounts the passcode screen in place of the site (W26-R20). Kept apart from main.ts so the screen and Vue's mount code are loaded only when a gate is closed.
import { createApp } from 'vue'
import GateScreen from './GateScreen.vue'

export function showGate(): void {
  createApp(GateScreen).mount('#app')
}
