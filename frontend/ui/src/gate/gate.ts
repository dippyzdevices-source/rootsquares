// The site gate, browser side (W26-R20, ADR 099). The server holds the gate (every API request needs the cookie a passcode earns); this file only asks
// "is there a gate and am I through it?" and sends the passcode. Both functions talk to `<api base>/gate` with the cookie (credentials: include).
// Used by the customer app and the admin application at start-up (see their main.ts); the square site has its own copy (a separate package).

export interface GateState { required: boolean; open: boolean; env: string }
export type GateResult = 'ok' | 'wrong' | 'limited' | 'error'

/** Is a gate on, and is this browser through it? null = the server did not answer (the app then starts and shows its own errors). */
export async function gateStatus(base: string): Promise<GateState | null> {
  try {
    const r = await fetch(`${base.replace(/\/$/, '')}/gate`, { credentials: 'include', headers: { Accept: 'application/json' } })
    if (!r.ok) return null
    const j = (await r.json()) as Partial<GateState>
    return { required: j.required === true, open: j.open === true, env: typeof j.env === 'string' ? j.env : '' }
  } catch {
    return null
  }
}

/** What the application needs at start-up: may it start (no gate, a pass, or the server cannot be asked), and the word of the environment strip. One request. */
export async function gateStart(base: string): Promise<{ open: boolean; env: string }> {
  const s = await gateStatus(base)
  return { open: !s || !s.required || s.open, env: s?.env ?? '' }
}

/** True when the app may start: no gate, or this browser has its pass, or the server cannot be asked. */
export async function gateIsOpen(base: string): Promise<boolean> {
  const s = await gateStatus(base)
  return !s || !s.required || s.open
}

/** Send the passcode. 'ok' means the server set the cookie. */
export async function gateEnter(base: string, passcode: string): Promise<GateResult> {
  try {
    const r = await fetch(`${base.replace(/\/$/, '')}/gate`, {
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
