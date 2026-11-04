// Tests for squareFavicon (5 cases), e.g. squareFavicon; draws the square's first letter in an SVG data URL; never lets markup from a name into the SVG, and copes with an empty na.
import { describe, it, expect } from 'vitest'
import { applySquareFavicon, squareFaviconHref } from '../squareFavicon'

describe('squareFavicon', () => {
  it("draws the square's first letter in an SVG data URL", () => {
    const href = decodeURIComponent(squareFaviconHref('first-org'))
    expect(href.startsWith('data:image/svg+xml,')).toBe(true)
    expect(href).toContain('>F</text>')
  })

  it('never lets markup from a name into the SVG, and copes with an empty name', () => {
    expect(decodeURIComponent(squareFaviconHref('<script>'))).not.toContain('<script>')
    expect(decodeURIComponent(squareFaviconHref('  '))).toContain('·')
  })

  it('sets the page icon link', () => {
    applySquareFavicon('Zeta')
    const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
    expect(link?.type).toBe('image/svg+xml')
    expect(decodeURIComponent(link?.href ?? '')).toContain('>Z</text>')
  })
  it('uses the uploaded logo as the page icon when the square has one (W6-R53)', () => {
    applySquareFavicon('Zeta', 'https://files.example/logo.png')
    const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
    expect(link?.href).toBe('https://files.example/logo.png')
    expect(link?.getAttribute('type')).toBeNull()
  })
})
