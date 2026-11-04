/**
 * What it is:   The owner's shared draft look, seen by the committee before it goes live (rootsquares W18-R47, docs/plans/themes-starting-looks-plan.md extra 2).
 * What it does: `?look=<token>` on any page of the site asks the square server for the draft (POST /api/square/look-draft; the token must match, a passcode is asked for when the owner set one)
 *               and shows the site with the draft instead of the live look, with a bar that says so. The token and the passcode are kept for the browser tab only; `?look=off` or "Leave the draft" forgets them.
 *               The draft carries the theme the owner had picked, so the whole site (its layout too) is the draft's. Visitors without the link never get the draft; the live look is not changed. The draft covers colours, fonts, shapes and feel (spinners are only shown once published).
 * How to use:   `const draft = await openDraftLook(window.location.search, window.sessionStorage, document)` while the square's profile is built (services/squareConfig.ts); it returns {look, themeId} or null.
 * Run:          from square/frontend: npx vitest run src/themes/draftLook.spec.ts
 * Read before:  src/themes/applyThemeOverrides.ts.
 * Read after:   src/services/squareConfig.ts.
 */
import type { ThemeOverrides } from './applyThemeOverrides'

export const TOKEN_KEY = 'rs-draft-look'
export const PASS_KEY = 'rs-draft-pass'
type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

/** The draft link's token: from `?look=` (and kept for the tab), else the kept one; `?look=off` forgets it. */
export function draftToken(search: string, storage: Store): string | null {
  const given = new URLSearchParams(search).get('look')
  if (given === 'off') { storage.removeItem(TOKEN_KEY); storage.removeItem(PASS_KEY); return null }
  if (given && /^[A-Za-z0-9_-]{8,100}$/.test(given)) {
    if (storage.getItem(TOKEN_KEY) !== given) storage.removeItem(PASS_KEY)
    storage.setItem(TOKEN_KEY, given)
    return given
  }
  const kept = storage.getItem(TOKEN_KEY)
  return kept && /^[A-Za-z0-9_-]{8,100}$/.test(kept) ? kept : null
}

export interface DraftView { look: ThemeOverrides; themeId: string | null }
export type DraftAnswer = { look: ThemeOverrides; theme_id?: string | null } | { error: 'passcode_required' | 'invalid' | 'expired' | 'too_many' | 'unreachable' }

/** One ask to the square server. */
export async function askDraft(token: string, passcode: string, fetcher: typeof fetch = fetch, base = ''): Promise<DraftAnswer> {
  try {
    const response = await fetcher(`${base}/api/square/look-draft`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token, passcode }) })
    const body = (await response.json().catch(() => ({}))) as { look?: ThemeOverrides; theme_id?: string | null; error?: string }
    if (response.ok && body.look) return { look: body.look, theme_id: body.theme_id ?? null }
    const error = body.error
    return { error: error === 'passcode_required' || error === 'expired' || error === 'too_many' ? error : 'invalid' }
  } catch {
    return { error: 'unreachable' }
  }
}

const BAR = 'position:fixed;inset:auto 0 0 0;z-index:2147483000;display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;justify-content:center;padding:10px 16px;background:#1f1a14;color:#fff;font:500 14px/1.4 system-ui,sans-serif;box-shadow:0 -2px 12px rgba(0,0,0,.35)'
const BTN = 'font:inherit;padding:4px 12px;border-radius:6px;border:1px solid #fff;background:transparent;color:#fff;cursor:pointer'

/** The bar at the bottom of a page that shows a draft. */
export function showDraftBar(doc: Document, onLeave: () => void): void {
  const bar = doc.createElement('div')
  bar.setAttribute('role', 'status')
  bar.setAttribute('style', BAR)
  const text = doc.createElement('span')
  text.textContent = 'Draft look — only people with this link see it. The public site is unchanged.'
  const leave = doc.createElement('button')
  leave.type = 'button'
  leave.setAttribute('style', BTN)
  leave.textContent = 'Leave the draft'
  leave.addEventListener('click', onLeave)
  bar.append(text, leave)
  doc.body.appendChild(bar)
}

/** Asks for the passcode in a small box; resolves with what was typed, or null when cancelled. */
export function askPasscode(doc: Document, note: string): Promise<string | null> {
  return new Promise((resolve) => {
    const wrap = doc.createElement('div')
    wrap.setAttribute('style', 'position:fixed;inset:0;z-index:2147483001;display:grid;place-items:center;background:#f5efe4') // nothing is drawn behind it yet, so the ground is the plain cream of the platform (TS-34)
    const form = doc.createElement('form')
    form.setAttribute('style', 'display:grid;gap:16px;width:min(420px,92vw);padding:26px;border:1px solid #e3d9c6;border-radius:16px;background:#fff;color:#1f1a14;font:400 16px/1.45 system-ui,sans-serif;box-shadow:0 12px 40px rgba(31,26,20,.18)')
    form.setAttribute('role', 'dialog')
    form.setAttribute('aria-modal', 'true')
    form.setAttribute('aria-label', note || 'This draft look needs a passcode')
    const label = doc.createElement('label')
    label.setAttribute('style', 'display:grid;gap:8px;font-weight:600')
    label.textContent = note || 'This draft look needs a passcode'
    const input = doc.createElement('input')
    input.type = 'password'
    input.autocomplete = 'off'
    input.setAttribute('style', 'font:inherit;font-weight:400;min-height:46px;padding:0 14px;border:1px solid #8a8272;border-radius:10px')
    label.appendChild(input)
    const row = doc.createElement('div')
    row.setAttribute('style', 'display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap')
    const cancel = doc.createElement('button')
    cancel.type = 'button'
    cancel.textContent = 'Cancel'
    cancel.setAttribute('style', 'font:600 11px system-ui,sans-serif;letter-spacing:.1em;text-transform:uppercase;min-height:44px;padding:0 22px;border:1px solid #cfc5ad;border-radius:999px;background:#fff;color:#1f1a14;cursor:pointer')
    const ok = doc.createElement('button')
    ok.type = 'submit'
    ok.textContent = 'Show the draft'
    ok.setAttribute('style', 'font:600 11px system-ui,sans-serif;letter-spacing:.1em;text-transform:uppercase;min-height:44px;padding:0 22px;border:0;border-radius:999px;background:#2b1a12;color:#efe3d0;cursor:pointer')
    row.append(cancel, ok)
    form.append(label, row)
    wrap.appendChild(form)
    doc.body.appendChild(wrap)
    input.focus()
    const done = (value: string | null) => { wrap.remove(); resolve(value) }
    cancel.addEventListener('click', () => done(null))
    form.addEventListener('submit', (e) => { e.preventDefault(); done(input.value) })
  })
}

/**
 * Opens the draft if the address or the tab carries a token. Returns the draft (look and theme), or null (no token, wrong or expired link, cancelled passcode: the live site shows, as for everybody).
 * The token leaves the address bar (it stays in the tab) so a screenshot or a copied address does not carry it.
 */
export async function openDraftLook(search: string, storage: Store, doc: Document, fetcher: typeof fetch = fetch, base = ''): Promise<DraftView | null> {
  const token = draftToken(search, storage)
  if (new URLSearchParams(search).has('look')) {
    try {
      const url = new URL(doc.location.href)
      url.searchParams.delete('look')
      doc.defaultView?.history.replaceState(null, '', url.pathname + url.search + url.hash)
    } catch { /* the address stays as it is */ }
  }
  if (!token) return null
  let passcode = storage.getItem(PASS_KEY) ?? ''
  let answer = await askDraft(token, passcode, fetcher, base)
  if ('error' in answer && answer.error === 'passcode_required') {
    for (let tries = 0; tries < 3 && 'error' in answer && answer.error === 'passcode_required'; tries += 1) {
      const typed = await askPasscode(doc, tries ? 'That passcode did not match. Try again' : '')
      if (typed === null) break
      passcode = typed
      answer = await askDraft(token, passcode, fetcher, base)
      if ('error' in answer && answer.error === 'invalid') answer = { error: 'passcode_required' }
    }
  }
  if (!('look' in answer)) { storage.removeItem(TOKEN_KEY); storage.removeItem(PASS_KEY); return null }
  if (passcode) storage.setItem(PASS_KEY, passcode)
  showDraftBar(doc, () => { storage.removeItem(TOKEN_KEY); storage.removeItem(PASS_KEY); doc.location.reload() })
  return { look: answer.look, themeId: typeof answer.theme_id === 'string' && /^[a-z0-9-]{1,60}$/.test(answer.theme_id) ? answer.theme_id : null }
}
