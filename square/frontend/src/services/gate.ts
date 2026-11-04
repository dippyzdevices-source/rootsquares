// The site gate, browser side (W26-R20, ADR 099). The server holds the gate; this file asks whether there is one and whether this browser is through it, and sends the
// passcode. Same-origin by default (the site calls /api on its own address); VITE_API_BASE_URL is honoured like the other services. A copy of the platform's
// frontend/ui/src/gate/gate.ts, because this package is separate.
export interface GateState { required: boolean; open: boolean }
export type GateResult = 'ok' | 'wrong' | 'limited' | 'error'

const base = (): string => ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '').replace(/\/$/, '')

export async function gateStatus(): Promise<GateState | null> {
  try {
    const r = await fetch(`${base()}/api/gate`, { credentials: 'include', headers: { Accept: 'application/json' } })
    if (!r.ok) return null
    const j = (await r.json()) as Partial<GateState>
    return { required: j.required === true, open: j.open === true }
  } catch {
    return null
  }
}

/** True when the site may start: no gate, this browser has its pass, or the server cannot be asked (the site then shows its own errors). */
export async function gateIsOpen(): Promise<boolean> {
  const s = await gateStatus()
  return !s || !s.required || s.open
}

export async function gateEnter(passcode: string): Promise<GateResult> {
  try {
    const r = await fetch(`${base()}/api/gate`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ passcode }),
    })
    if (r.ok) return 'ok'
    if (r.status === 429) return 'limited'
    return r.status === 401 ? 'wrong' : 'error'
  } catch {
    return 'error'
  }
}
