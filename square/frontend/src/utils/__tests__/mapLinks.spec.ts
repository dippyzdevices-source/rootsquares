// Tests for mapLinks (3 cases), e.g. mapLinks; drops a "c/o <person>" line so the map can find the street; builds keyless embed, open and directions URLs from the cleaned addres.
import { describe, it, expect } from 'vitest'
import { mappableAddress, mapEmbedUrl, mapOpenUrl, mapDirectionsUrl } from '../mapLinks'

describe('mapLinks', () => {
  it('drops a "c/o <person>" line so the map can find the street', () => {
    expect(mappableAddress('c/o Niladri Malakar, Bølerlia 6, 0691 OSLO')).toBe('Bølerlia 6, 0691 OSLO')
    expect(mappableAddress('Storgata 1, 0155 Oslo')).toBe('Storgata 1, 0155 Oslo')
  })

  it('builds keyless embed, open and directions URLs from the cleaned address', () => {
    const q = encodeURIComponent('Bølerlia 6, 0691 OSLO')
    const address = 'c/o Niladri Malakar, Bølerlia 6, 0691 OSLO'
    expect(mapEmbedUrl(address)).toBe(`https://maps.google.com/maps?q=${q}&output=embed`)
    expect(mapOpenUrl(address)).toBe(`https://www.google.com/maps/search/?api=1&query=${q}`)
    expect(mapDirectionsUrl(address)).toBe(`https://www.google.com/maps/dir/?api=1&destination=${q}`)
  })
})
