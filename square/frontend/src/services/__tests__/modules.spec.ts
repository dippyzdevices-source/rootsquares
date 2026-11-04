// Tests for modules (5 cases), e.g. modules (W8-R9); knows which module a page belongs to, core pages belong to none; shows a page only when its module is on.
import { describe, it, expect, vi } from 'vitest'

vi.mock('../squareConfig', () => ({ squareProfile: { modules: ['news', 'gallery'] } }))

import { MODULE_KEYS, moduleEnabled, moduleForPath, offeredPhrase, pathAvailable } from '../modules'

describe('modules (W8-R9)', () => {
  it('knows which module a page belongs to, core pages belong to none', () => {
    expect(moduleForPath('/events')).toBe('events')
    expect(moduleForPath('/events/summer-fest')).toBe('events')
    expect(moduleForPath('/events/summer-fest/tickets')).toBe('tickets')
    expect(moduleForPath('/news/magazines/may')).toBe('magazines')
    expect(moduleForPath('/news/my-story')).toBe('news')
    expect(moduleForPath('/membership')).toBe('memberships')
    expect(moduleForPath('/membership-drive')).toBe('memberships')
    expect(moduleForPath('/admin/members/12')).toBe('members')
    expect(moduleForPath('/admin/members/import')).toBe('memberships') // the Excel import creates memberships (ADR 044)
    expect(moduleForPath('/admin/members/follow-up')).toBe('memberships')
    expect(moduleForPath('/admin/content/pages/membership')).toBe('memberships')
    expect(moduleForPath('/member/family')).toBe('memberships')
    expect(moduleForPath('/admin/volunteers')).toBe('checkin')
    expect(moduleForPath('/member/volunteering')).toBe('volunteering')
    // The always-on parts are keys of their own since W19-R24 (a custom package may leave them out); only an unknown path belongs to nothing
    const core: Record<string, string> = { '/': 'home', '/about': 'about', '/contact': 'contact', '/login': 'login', '/privacy': 'legal', '/admin': 'admin', '/admin/content': 'admin', '/admin/content/pages/about': 'about', '/member': 'account', '/member/settings': 'account' }
    for (const [path, key] of Object.entries(core)) expect(moduleForPath(path)).toBe(key)
    expect(moduleForPath('/eventsfoo')).toBeUndefined()
  })

  it('shows a page only when its module is on', () => {
    expect(moduleEnabled('news')).toBe(true)
    expect(moduleEnabled('events')).toBe(false)
    expect(moduleEnabled(undefined)).toBe(true)
    expect(pathAvailable('/news')).toBe(true)
    expect(pathAvailable('/events/x')).toBe(false)
    expect(pathAvailable('/events/x/tickets')).toBe(false)
    expect(pathAvailable('/contact')).toBe(true)
  })

  it('lists the same modules as the backend, 19 of them', () => {
    expect(MODULE_KEYS).toHaveLength(19)
    expect(new Set(MODULE_KEYS).size).toBe(19)
  })

  it('names what the square offers in a phrase (here only news is on)', () => {
    expect(offeredPhrase()).toBe('news')
  })
})
