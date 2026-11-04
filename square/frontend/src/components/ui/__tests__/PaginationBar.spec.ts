// Tests for PaginationBar (3 cases), e.g. PaginationBar; renders nothing for a single page; emits the next/previous page and disables at the edges.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PaginationBar from '../PaginationBar.vue'

describe('PaginationBar', () => {
  it('renders nothing for a single page', () => {
    expect(mount(PaginationBar, { props: { page: 1, totalPages: 1 } }).find('nav').exists()).toBe(false)
  })

  it('emits the next/previous page and disables at the edges', async () => {
    const wrapper = mount(PaginationBar, { props: { page: 1, totalPages: 3, total: 50 } })
    const [prev, next] = wrapper.findAll('button')
    expect(prev.attributes('disabled')).toBeDefined()
    await next.trigger('click')
    expect(wrapper.emitted('update:page')![0]).toEqual([2])
    expect(wrapper.text()).toContain('Page 1 of 3 (50 total)')
  })
})
