// Tests for usePageMeta (8 cases), e.g. setPageMeta; sets the document title with the site suffix; falls back to the bare site name when no title is given.
import { describe, it, expect, beforeEach } from 'vitest'
import { setBackSoonMeta, setPageMeta } from '../usePageMeta'

beforeEach(() => {
  document.title = ''
  document.querySelectorAll('meta[name="description"], meta[name="robots"]').forEach((el) => el.remove())
})

describe('setPageMeta', () => {
  it('sets the document title with the site suffix', () => {
    setPageMeta('Events')

    expect(document.title).toBe('Events — BCA Oslo')
  })

  it('falls back to the bare site name when no title is given', () => {
    setPageMeta('')

    expect(document.title).toBe('BCA Oslo')
  })

  it('creates a meta description tag when one does not exist', () => {
    setPageMeta('Events', 'See upcoming BCA Oslo events.')

    const tag = document.querySelector('meta[name="description"]')
    expect(tag?.getAttribute('content')).toBe('See upcoming BCA Oslo events.')
  })

  it('updates an existing meta description tag rather than duplicating it', () => {
    setPageMeta('Events', 'First description.')
    setPageMeta('About', 'Second description.')

    const tags = document.querySelectorAll('meta[name="description"]')
    expect(tags).toHaveLength(1)
    expect(tags[0].getAttribute('content')).toBe('Second description.')
  })

  it('leaves the existing meta description untouched when none is given', () => {
    setPageMeta('Events', 'Keep me.')
    setPageMeta('About')

    const tag = document.querySelector('meta[name="description"]')
    expect(tag?.getAttribute('content')).toBe('Keep me.')
  })
})


describe('setBackSoonMeta', () => {
  it('titles the tab "back soon" and asks search engines not to index the resting page, once', () => {
    setBackSoonMeta()
    setBackSoonMeta()

    expect(document.title).toBe('BCA Oslo — back soon')
    const tags = document.querySelectorAll('meta[name="robots"]')
    expect(tags).toHaveLength(1)
    expect(tags[0].getAttribute('content')).toBe('noindex')
  })
})
