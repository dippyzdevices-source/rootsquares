// Tests for useSettingsGroup (4 cases), e.g. groupForRoute; maps every Settings sub-page (and its nested pages) to its high-level; uses ?group= on the hub and defaults to Site.
import { describe, it, expect } from 'vitest'
import { groupForRoute, settingsBackTarget } from '../useSettingsGroup'

describe('groupForRoute', () => {
  it('maps every Settings sub-page (and its nested pages) to its high-level group', () => {
    expect(groupForRoute('/admin/content/contact-details', undefined)).toBe('site')
    expect(groupForRoute('/admin/content/payments', undefined)).toBe('site')
    expect(groupForRoute('/admin/content/lists', undefined)).toBe('lists')
    expect(groupForRoute('/admin/content/committee', undefined)).toBe('people')
    expect(groupForRoute('/admin/content/committee/new', undefined)).toBe('people')
    expect(groupForRoute('/admin/content/founders/3/edit', undefined)).toBe('people')
    expect(groupForRoute('/admin/content/heritage-image', undefined)).toBe('pages')
    expect(groupForRoute('/admin/content/sponsors/2/edit', undefined)).toBe('people')
    expect(groupForRoute('/admin/content/pages/about', undefined)).toBe('pages')
    expect(groupForRoute('/admin/content/header-footer', undefined)).toBe('site') // W6-R74
    expect(groupForRoute('/admin/content/home', undefined)).toBe('pages')
    expect(groupForRoute('/admin/content/legal-texts', undefined)).toBe('pages')
  })

  it('uses ?group= on the hub and defaults to Site', () => {
    expect(groupForRoute('/admin/content', 'people')).toBe('people')
    expect(groupForRoute('/admin/content', 'pages')).toBe('pages')
    expect(groupForRoute('/admin/content', 'nonsense')).toBe('site')
    expect(groupForRoute('/admin/content', undefined)).toBe('site')
  })

  it('gives a Back button on sub-pages to their tab; none on the hub, Lists or a form (forms have their own) (W8-R4)', () => {
    expect(settingsBackTarget('/admin/content', 'site')).toBeNull()
    expect(settingsBackTarget('/admin/content/lists', 'lists')).toBeNull()
    expect(settingsBackTarget('/admin/content/pages/about', 'pages')).toEqual({ to: { path: '/admin/content', query: { group: 'pages' } }, label: 'Back to Pages & media' })
    expect(settingsBackTarget('/admin/content/sponsors', 'people')).toEqual({ to: { path: '/admin/content', query: { group: 'people' } }, label: 'Back to People' })
    expect(settingsBackTarget('/admin/content/sponsors/2/edit', 'people')).toBeNull()
    expect(settingsBackTarget('/admin/content/committee/new', 'people')).toBeNull()
  })
})
