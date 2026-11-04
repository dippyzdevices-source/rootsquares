// Tests for scheduleDays (4 cases), e.g. groupSessionsByDay; groups items under their day, keeping the order they arrive in; shows a free-text day label as typed.
import { describe, expect, it } from 'vitest'
import { groupSessionsByDay } from '../scheduleDays'

describe('groupSessionsByDay', () => {
  it('groups items under their day, keeping the order they arrive in', () => {
    const groups = groupSessionsByDay([
      { id: 1, day_label: '2026-10-17', title: 'a' },
      { id: 2, day_label: '2026-10-16', title: 'b' },
      { id: 3, day_label: '2026-10-17', title: 'c' },
    ])
    expect(groups.map((g) => g.key)).toEqual(['2026-10-17', '2026-10-16'])
    expect(groups[0].items.map((i) => i.id)).toEqual([1, 3])
    expect(groups[0].label).toBe('Saturday 17 Oct')
  })

  it('shows a free-text day label as typed', () => {
    const [group] = groupSessionsByDay([{ day_label: 'Day 1 - Sasthi' }])
    expect(group.label).toBe('Day 1 - Sasthi')
  })

  it('returns no groups for an empty schedule', () => {
    expect(groupSessionsByDay([])).toEqual([])
  })
})
