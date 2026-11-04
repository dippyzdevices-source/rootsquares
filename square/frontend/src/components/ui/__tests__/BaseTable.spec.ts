// Tests for BaseTable (4 cases), e.g. BaseTable; renders one row per item and the raw cell value by default; shows an empty state instead of a table when rows is empty.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { h } from 'vue'
import BaseTable from '../BaseTable.vue'

const columns = [
  { key: 'name', label: 'Name' },
  { key: 'status', label: 'Status' },
]

describe('BaseTable', () => {
  it('renders one row per item and the raw cell value by default', () => {
    const rows = [
      { name: 'Alice', status: 'Active' },
      { name: 'Bob', status: 'Expired' },
    ]
    const wrapper = mount(BaseTable, { props: { columns, rows } })

    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Expired')
  })

  it('shows an empty state instead of a table when rows is empty', () => {
    const wrapper = mount(BaseTable, {
      props: { columns, rows: [], emptyMessage: 'No members yet' },
    })

    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.text()).toContain('No members yet')
  })

  it('renders a custom cell via the named scoped slot', () => {
    const rows = [{ name: 'Alice', status: 'Active' }]
    const wrapper = mount(BaseTable, {
      props: { columns, rows },
      slots: {
        'cell-status': (slotProps: { row: Record<string, unknown> }) =>
          h('b', `${slotProps.row.status}!!`),
      },
    })

    expect(wrapper.find('b').text()).toBe('Active!!')
  })
})
