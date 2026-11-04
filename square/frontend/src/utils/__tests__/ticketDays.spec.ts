// Tests for ticketDays (3 cases), e.g. groupTicketsByDay; returns one unlabelled group when no ticket has a date; sections by day in date order, with undated tickets last under All day.
import { describe, it, expect } from 'vitest'
import { groupTicketsByDay } from '../ticketDays'

describe('groupTicketsByDay', () => {
  it('returns one unlabelled group when no ticket has a date', () => {
    const groups = groupTicketsByDay([{ valid_on: null }, {}])
    expect(groups).toHaveLength(1)
    expect(groups[0].label).toBe('')
    expect(groups[0].items).toHaveLength(2)
  })

  it('sections by day in date order, with undated tickets last under All days', () => {
    const groups = groupTicketsByDay([
      { id: 1, valid_on: '2026-10-24' },
      { id: 2, valid_on: null },
      { id: 3, valid_on: '2026-10-23' },
      { id: 4, valid_on: '2026-10-24' },
    ])
    expect(groups.map((g) => g.label)).toEqual(['Friday 23 Oct', 'Saturday 24 Oct', 'All days'])
    expect(groups[1].items.map((i) => i.id)).toEqual([1, 4])
  })
})
