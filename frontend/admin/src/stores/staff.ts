import { defineStore } from 'pinia'
import { ref } from 'vue'
import { staffApi, type StaffMember, type StaffSessionInfo, type StaffStep } from '@/adminApi'

// Who is signed in to the admin application (ADR 083): a staff member and how far the sign-in has come (password done, second step asked, done).
// The server decides; this store only holds its last answer. Not the customer's auth store: staff and customers never share a session.
export const useStaffStore = defineStore('staff', () => {
  const user = ref<StaffMember | null>(null)
  const step = ref<StaffStep | null>(null)
  const loaded = ref(false)
  let pending: Promise<void> | null = null

  function apply(info: StaffSessionInfo) { user.value = info.staff; step.value = info.step; loaded.value = true }
  function clear() { user.value = null; step.value = null; loaded.value = true }

  /** Ask the server once who is signed in; the router guard waits for it. */
  function load(): Promise<void> {
    if (loaded.value) return Promise.resolve()
    pending ??= staffApi.me().then(apply, clear).finally(() => { loaded.value = true })
    return pending
  }
  async function login(email: string, password: string) { apply(await staffApi.login(email, password)) }
  async function totp(code: string) { apply(await staffApi.totp(code)) }
  async function logout() {
    try { await staffApi.logout() } finally { clear() }
  }
  return { user, step, loaded, load, apply, clear, login, totp, logout }
})
