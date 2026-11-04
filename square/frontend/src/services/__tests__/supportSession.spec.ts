// A rootsquares support session in the browser (ADR 089, W23-R66): the token leaves the address at once, it stands in for a sign-in, a read only session never writes, and the
// end of the access is reported. The server decides everything; these tests keep the page honest.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { MiniAuthClient } from '../neonAuthAdapter'
import {
  captureSupportToken,
  endSupportSession,
  inSupportSession,
  installSupportFetch,
  onSupportMessage,
  setSupportMode,
  supportToken,
  withSupport,
} from '../supportSession'

const realClient = (): MiniAuthClient =>
  ({
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'own', user: { id: 'u1' } } } }),
      onAuthStateChange: vi.fn(),
      signOut: vi.fn().mockResolvedValue({ error: null }),
    },
  }) as unknown as MiniAuthClient

beforeEach(() => {
  window.sessionStorage.clear()
  window.history.replaceState(null, '', '/admin')
  setSupportMode(null)
})
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('capturing the token', () => {
  it('takes the token out of the address, keeps it for this tab and leaves no trace in the address', () => {
    window.history.replaceState(null, '', '/admin#support=abc.def.ghi')
    expect(captureSupportToken()).toBe(true)
    expect(supportToken()).toBe('abc.def.ghi')
    expect(window.location.hash).toBe('')
    expect(window.location.pathname).toBe('/admin')
  })

  it('does nothing for an address without a token or with an empty one', () => {
    expect(captureSupportToken()).toBe(false)
    window.history.replaceState(null, '', '/admin#support=')
    expect(captureSupportToken()).toBe(false)
    expect(inSupportSession()).toBe(false)
  })

  it('ending the session forgets the token', () => {
    window.sessionStorage.setItem('rs_support_token', 'abc')
    endSupportSession()
    expect(inSupportSession()).toBe(false)
  })
})

describe('standing in for the sign-in', () => {
  it('leaves the real client alone when there is no support session', () => {
    const client = realClient()
    expect(withSupport(client)).toBe(client)
  })

  it('answers with the support token as the session, and signing out ends the support session', async () => {
    window.sessionStorage.setItem('rs_support_token', 'tok')
    const wrapped = withSupport(realClient())
    const { data } = await wrapped.auth.getSession()
    expect(data.session?.access_token).toBe('tok')
    await wrapped.auth.signOut()
    expect((await wrapped.auth.getSession()).data.session).toBeNull()
  })
})

describe('the page never writes in a read only session', () => {
  it('refuses a change without asking the server, says so, and passes reads through', async () => {
    window.sessionStorage.setItem('rs_support_token', 'tok')
    const server = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }))
    const win = { fetch: server } as unknown as Window
    installSupportFetch(win)
    const said: string[] = []
    onSupportMessage((m) => said.push(m))
    setSupportMode({ name: 'Anna', scopes: ['content'], allow_changes: false, ends_at: '2026-10-27T12:00:00Z' })

    const refused = await win.fetch('/api/admin/news', { method: 'POST', body: '{}' })
    expect(refused.status).toBe(403)
    expect((await refused.json()).code).toBe('support_read_only')
    expect(server).not.toHaveBeenCalled()
    expect(said.at(-1)).toMatch(/read only/)

    expect((await win.fetch('/api/admin/news')).status).toBe(200)
    expect(server).toHaveBeenCalledTimes(1)
  })

  it('lets a change through when the owner allowed changes (the server still decides)', async () => {
    window.sessionStorage.setItem('rs_support_token', 'tok')
    const server = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
    const win = { fetch: server } as unknown as Window
    installSupportFetch(win)
    setSupportMode({ name: 'Anna', scopes: ['content'], allow_changes: true, ends_at: '2026-10-27T12:00:00Z' })
    expect((await win.fetch('/api/admin/news', { method: 'PUT', body: '{}' })).status).toBe(200)
    expect(server).toHaveBeenCalledTimes(1)
  })

  it('reports the end of the access and forgets the token when the server says it is over', async () => {
    window.sessionStorage.setItem('rs_support_token', 'tok')
    const body = JSON.stringify({ error: 'The support access has ended.', code: 'support_ended' })
    const win = { fetch: vi.fn().mockResolvedValue(new Response(body, { status: 403 })) } as unknown as Window
    installSupportFetch(win)
    const said: string[] = []
    onSupportMessage((m) => said.push(m))
    await win.fetch('/api/admin/news')
    expect(inSupportSession()).toBe(false)
    expect(said.at(-1)).toBe('The support access has ended.')
  })

  it('is not installed at all outside a support session', () => {
    const original = vi.fn()
    const win = { fetch: original } as unknown as Window
    installSupportFetch(win)
    expect(win.fetch).toBe(original)
  })
})
