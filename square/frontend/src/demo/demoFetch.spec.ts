// Tests for demoFetch (9 cases), e.g. demo mode answers; configures a neutral square with an auth host that never answers; lists upcoming and past events, with details and ticket types.
import { afterEach, describe, expect, it } from 'vitest'
import { demoAnswer } from './demoFetch'
import { installDemoFetch } from './install'

const get = (path: string, query = '') => demoAnswer('GET', path, new URLSearchParams(query))
const body = <T>(path: string, query = '') => {
  const a = get(path, query)
  expect(a.status).toBe(200)
  return a.body as T
}
const demoImage = (url: string | null) => expect(url).toMatch(/^\/demo\/photo-\d+\.jpg$/)

describe('demo mode answers', () => {
  it('configures a neutral square with an auth host that never answers', () => {
    const c = body<{ name: string; slug: string; theme_id: string; auth: { url: string }; modules: string[]; logo_url: string }>('/api/square/config')
    expect(c.name).toBe('Sample Society')
    expect(c.slug).toBe('demo')
    expect(c.auth.url).toBe('https://demo.invalid')
    expect(c.logo_url).toBe('')
    expect(c.modules).toContain('gallery')
    expect(demoAnswer('GET', '/api/square/config', new URLSearchParams(), 'atrium').body).toMatchObject({ theme_id: 'atrium' })
  })

  it('lists upcoming and past events, with details and ticket types', () => {
    const upcoming = body<{ items: { slug: string; start_datetime: string; banner_image: string }[]; total_pages: number }>('/api/events', 'when=upcoming&per_page=3')
    expect(upcoming.items).toHaveLength(3)
    upcoming.items.forEach((e) => { expect(Date.parse(e.start_datetime)).toBeGreaterThan(Date.now()); demoImage(e.banner_image) })
    const past = body<{ items: { start_datetime: string }[] }>('/api/events', 'when=past')
    expect(past.items.length).toBeGreaterThan(0)
    past.items.forEach((e) => expect(Date.parse(e.start_datetime)).toBeLessThan(Date.now()))
    const detail = body<{ id: number; slug: string; banners: { image_url: string }[]; sessions: unknown[] }>(`/api/events/${upcoming.items[0]!.slug}`)
    demoImage(detail.banners[0]!.image_url)
    const tickets = body<{ items: { price: number }[] }>('/api/tickets/types', `event_id=${detail.id}`)
    expect(tickets.items.length).toBeGreaterThan(0)
    expect(get('/api/events/nope').status).toBe(404)
  })

  it('serves gallery albums, an album, the media strip and the coverage list', () => {
    const albums = body<{ items: { id: number; cover_thumbnail_url: string; photo_count: number }[] }>('/api/gallery/albums')
    expect(albums.items.length).toBeGreaterThanOrEqual(4)
    albums.items.forEach((a) => demoImage(a.cover_thumbnail_url))
    const album = body<{ media: { url: string; thumbnail_url: string }[] }>(`/api/gallery/albums/${albums.items[0]!.id}`)
    expect(album.media.length).toBe(albums.items[0]!.photo_count)
    album.media.forEach((m) => { demoImage(m.url); demoImage(m.thumbnail_url) })
    expect(body<{ items: unknown[] }>('/api/gallery/media', 'limit=5').items).toHaveLength(5)
    expect(body<{ items: unknown[] }>('/api/gallery/coverage').items.length).toBeGreaterThan(0)
    expect(get('/api/gallery/albums/999').status).toBe(404)
  })

  it('serves news, people, partners, magazines and membership types', () => {
    const news = body<{ items: { slug: string; banner_image: string; published_at: string }[] }>('/api/news')
    expect(news.items.length).toBeGreaterThanOrEqual(3)
    news.items.forEach((n) => { demoImage(n.banner_image); expect(Number.isNaN(Date.parse(n.published_at))).toBe(false) })
    expect(body<{ content: string }>(`/api/news/${news.items[0]!.slug}`).content.length).toBeGreaterThan(20)
    expect(body<{ items: { portrait_url: string | null }[] }>('/api/committee').items).toHaveLength(6)
    expect(body<{ items: unknown[] }>('/api/founders').items.length).toBeGreaterThan(0)
    expect(body<{ items: unknown[] }>('/api/sponsors').items).toHaveLength(3)
    expect(body<{ items: unknown[] }>('/api/testimonials').items).toHaveLength(3)
    const magazines = body<{ items: { slug: string; cover_url: string }[] }>('/api/magazines')
    magazines.items.forEach((m) => demoImage(m.cover_url))
    expect(body<{ slug: string }>(`/api/magazines/${magazines.items[0]!.slug}`).slug).toBe(magazines.items[0]!.slug)
    expect(body<{ items: { name: string }[] }>('/api/memberships/types').items.map((t) => t.name)).toEqual(['Individual', 'Family', 'Supporter'])
  })

  it('holds the words of the pages and the lookup lists', () => {
    const s = body<{ contact_email: string; heritage_image_url: string; home_content: { headline: string; about_page: { values: unknown[] } } }>('/api/settings')
    expect(s.contact_email).toMatch(/@example\.org$/)
    demoImage(s.heritage_image_url)
    expect(s.home_content.headline).not.toBe('')
    expect(s.home_content.about_page.values.length).toBeGreaterThan(0)
    expect(body<{ items: { value: string }[] }>('/api/lookups/event_type').items.map((i) => i.value)).toContain('festival')
  })

  it('refuses writes, signs the visitor out and answers unknown reads with 404', () => {
    expect(demoAnswer('POST', '/api/contact', new URLSearchParams()).status).toBe(403)
    expect(demoAnswer('PUT', '/api/members/me', new URLSearchParams()).status).toBe(403)
    expect(get('/api/auth/me').status).toBe(401)
    expect(get('/api/admin/events').status).toBe(401)
    expect(get('/api/does/not/exist').status).toBe(404)
  })
})

describe('installDemoFetch', () => {
  let undo: (() => void) | null = null
  afterEach(() => { undo?.(); undo = null })

  it('answers API and auth-host calls without touching the network and passes everything else through', async () => {
    const seen: string[] = []
    const original = window.fetch
    window.fetch = (async (input: RequestInfo | URL) => { seen.push(String(input)); return new Response('real') }) as typeof fetch
    undo = installDemoFetch()
    const r = await fetch('http://localhost:5002/api/events?when=upcoming')
    expect(r.status).toBe(200)
    expect(((await r.json()) as { items: unknown[] }).items.length).toBeGreaterThan(0)
    expect((await fetch('/api/contact', { method: 'POST', body: '{}' })).status).toBe(403)
    expect((await fetch('https://demo.invalid/token')).status).toBe(401)
    expect(await (await fetch('/demo/photo-10.jpg')).text()).toBe('real')
    expect(seen).toEqual(['/demo/photo-10.jpg'])
    undo()
    undo = null
    window.fetch = original
  })
})
