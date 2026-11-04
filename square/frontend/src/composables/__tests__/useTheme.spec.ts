// Tests for useTheme (7 cases), e.g. useTheme; defaults to light when nothing is stored; restores a previously stored theme.
import { describe, it, expect, beforeEach } from 'vitest'
import { useTheme } from '../useTheme'

beforeEach(() => {
  localStorage.clear()
  document.documentElement.classList.remove('dark')
})

describe('useTheme', () => {
  it('defaults to light when nothing is stored', () => {
    const { theme, initTheme } = useTheme()
    initTheme()

    expect(theme.value).toBe('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('restores a previously stored theme', () => {
    localStorage.setItem('bca-theme', 'dark')
    const { theme, initTheme } = useTheme()
    initTheme()

    expect(theme.value).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('ignores an invalid stored value and falls back to light', () => {
    localStorage.setItem('bca-theme', 'not-a-real-theme')
    const { theme, initTheme } = useTheme()
    initTheme()

    expect(theme.value).toBe('light')
  })

  it('setTheme("dark") adds the dark class and persists the choice', () => {
    const { theme, setTheme } = useTheme()
    setTheme('dark')

    expect(theme.value).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('bca-theme')).toBe('dark')
  })

  it('setTheme("light") removes the dark class', () => {
    const { setTheme } = useTheme()
    setTheme('dark')
    setTheme('light')

    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('bca-theme')).toBe('light')
  })

  it('does not throw when localStorage is unavailable', () => {
    const original = Storage.prototype.setItem
    Storage.prototype.setItem = () => {
      throw new Error('blocked')
    }

    const { setTheme } = useTheme()
    expect(() => setTheme('dark')).not.toThrow()

    Storage.prototype.setItem = original
  })
})
