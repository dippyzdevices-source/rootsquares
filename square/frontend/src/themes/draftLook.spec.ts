// Scoped tests of the shared draft look (W18-R47): the token handling, the ask to the server, and the bar.
import { beforeEach, describe, expect, it } from 'vitest'
import { PASS_KEY, TOKEN_KEY, askDraft, draftToken, openDraftLook } from './draftLook'

class Mem {
  data: Record<string, string> = {}
  getItem(k: string) { return k in this.data ? this.data[k] : null }
  setItem(k: string, v: string) { this.data[k] = v }
  removeItem(k: string) { delete this.data[k] }
}
const TOKEN = 'abcdefgh12345678'
const reply = (status: number, body: object) => (async () => new Response(JSON.stringify(body), { status })) as unknown as typeof fetch

describe('draftToken', () => {
  it('takes ?look= and keeps it for the tab, ?look=off forgets it, a bad token is ignored', () => {
    const s = new Mem()
    expect(draftToken('', s)).toBeNull()
    expect(draftToken(`?look=${TOKEN}`, s)).toBe(TOKEN)
    expect(draftToken('', s)).toBe(TOKEN)
    s.setItem(PASS_KEY, 'garden')
    expect(draftToken('?look=off', s)).toBeNull()
    expect(s.getItem(TOKEN_KEY)).toBeNull()
    expect(s.getItem(PASS_KEY)).toBeNull()
    expect(draftToken('?look=<script>', new Mem())).toBeNull()
  })
  it('a different link forgets the old passcode', () => {
    const s = new Mem()
    draftToken(`?look=${TOKEN}`, s)
    s.setItem(PASS_KEY, 'garden')
    draftToken('?look=zzzzzzzz99999999', s)
    expect(s.getItem(PASS_KEY)).toBeNull()
  })
})

describe('askDraft', () => {
  it('gives the look, or the reason', async () => {
    expect(await askDraft(TOKEN, '', reply(200, { look: { fonts: 'bold' }, theme_id: 'pearl' }))).toEqual({ look: { fonts: 'bold' }, theme_id: 'pearl' })
    expect(await askDraft(TOKEN, '', reply(401, { error: 'passcode_required' }))).toEqual({ error: 'passcode_required' })
    expect(await askDraft(TOKEN, '', reply(410, { error: 'expired' }))).toEqual({ error: 'expired' })
    expect(await askDraft(TOKEN, '', reply(403, { error: 'invalid' }))).toEqual({ error: 'invalid' })
    expect(await askDraft(TOKEN, '', (async () => { throw new Error('offline') }) as unknown as typeof fetch)).toEqual({ error: 'unreachable' })
  })
})

describe('openDraftLook', () => {
  beforeEach(() => { document.body.innerHTML = '' })
  it('shows the bar and takes the token out of the address when the draft opens', async () => {
    window.history.replaceState(null, '', `/?look=${TOKEN}&x=1`)
    const s = new Mem()
    const draft = await openDraftLook(window.location.search, s, document, reply(200, { look: { fonts: 'bold' }, theme_id: 'pearl' }))
    expect(draft).toEqual({ look: { fonts: 'bold' }, themeId: 'pearl' })
    expect(document.body.textContent).toContain('Draft look')
    expect(window.location.search).toBe('?x=1')
    expect(s.getItem(TOKEN_KEY)).toBe(TOKEN)
  })
  it('shows the live site (null, no bar) for a wrong or expired link and forgets it', async () => {
    const s = new Mem()
    expect(await openDraftLook(`?look=${TOKEN}`, s, document, reply(403, { error: 'invalid' }))).toBeNull()
    expect(document.body.textContent).not.toContain('Draft look')
    expect(s.getItem(TOKEN_KEY)).toBeNull()
  })
  it('asks nothing without a token', async () => {
    let asked = false
    const f = (async () => { asked = true; return new Response('{}') }) as unknown as typeof fetch
    expect(await openDraftLook('', new Mem(), document, f)).toBeNull()
    expect(asked).toBe(false)
  })
})
