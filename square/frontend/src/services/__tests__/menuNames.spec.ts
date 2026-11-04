// The names a square gives its public pages (W11-R43): the menu, the footer and the tab follow them; an empty name keeps the default.
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockFetchSettings = vi.fn()
vi.mock('../settingsApi', () => ({ fetchSettings: () => mockFetchSettings() }))

import { loadHomeContent, menuName, resetHomeContent } from '../siteContent'
import { navItems } from '../../layout-themes/useSiteLayout'

beforeEach(() => {
  resetHomeContent()
  mockFetchSettings.mockReset()
})

describe('menuName', () => {
  it('is the default until the square sets a name, then the square name', async () => {
    mockFetchSettings.mockResolvedValue({ home_content: { page_headings: { heritage: { nav_label: 'Peek Us' }, events: { title: 'What is on' } } } })
    expect(menuName('heritage', 'About')).toBe('About')
    await loadHomeContent()
    expect(menuName('heritage', 'About')).toBe('Peek Us')
    expect(menuName('events', 'Events')).toBe('Events') // a title is not a menu name
  })

  it('the themed menu follows it without being rebuilt', async () => {
    mockFetchSettings.mockResolvedValue({ home_content: { page_headings: { heritage: { nav_label: 'Peek Us' } } } })
    await loadHomeContent()
    const label = (key: string) => navItems.find((n) => n.key === key)?.label
    expect(label('heritage')).toBe('Peek Us')
    expect(label('contact')).toBe('Contact')
    expect(label('home')).toBe('Home')
  })
})
