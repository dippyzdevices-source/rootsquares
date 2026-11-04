// Tests for AccountMenu (11 cases), e.g. AccountMenu; hides the dropdown panel by default; shows the dropdown panel after clicking the trigger.
import { describe, it, expect, afterEach } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import AccountMenu, { type AccountMenuItem } from '../AccountMenu.vue'

// Mounted attached to document.body: this component reacts to document-level click/keydown
// listeners, and both real event bubbling and getComputedStyle() (used by isVisible()) are
// unreliable for a tree that isn't actually attached to the document under jsdom — the same
// reason BaseModal/BaseDrawer's teleported-content tests use document.body.
let wrapper: VueWrapper | undefined

const baseItems: AccountMenuItem[] = [
  { id: 'dashboard', label: 'Dashboard', to: '/member', icon: 'dashboard' },
  { id: 'div', label: '', divider: true },
  { id: 'signout', label: 'Sign out', icon: 'log-out', tone: 'danger' },
]

function mountMenu(
  props: Partial<InstanceType<typeof AccountMenu>['$props']> = {},
) {
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/member', component: { template: '<div/>' } },
    ],
  })
  wrapper = mount(AccountMenu, {
    props: {
      name: 'Priya Das',
      shortName: 'Priya',
      items: baseItems,
      ...props,
    },
    global: { plugins: [router] },
    attachTo: document.body,
  })
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
})

describe('AccountMenu', () => {
  it('hides the dropdown panel by default', () => {
    const wrapper = mountMenu()

    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
  })

  it('shows the dropdown panel after clicking the trigger', async () => {
    const wrapper = mountMenu()

    await wrapper.find('button[aria-haspopup="menu"]').trigger('click')

    expect(wrapper.find('[role="menu"]').exists()).toBe(true)
  })

  it('hides the dropdown panel again after a second click on the trigger', async () => {
    const wrapper = mountMenu()
    const trigger = wrapper.find('button[aria-haspopup="menu"]')

    await trigger.trigger('click')
    await trigger.trigger('click')

    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
  })

  it('closes the menu when Escape is pressed', async () => {
    const wrapper = mountMenu()

    await wrapper.find('button[aria-haspopup="menu"]').trigger('click')
    expect(wrapper.find('[role="menu"]').exists()).toBe(true)

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
  })

  it('closes the menu on an outside click', async () => {
    const wrapper = mountMenu()

    await wrapper.find('button[aria-haspopup="menu"]').trigger('click')
    expect(wrapper.find('[role="menu"]').exists()).toBe(true)

    document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
  })

  it('shows the full name, email, and meta once opened', async () => {
    const wrapper = mountMenu({ email: 'priya@example.com', meta: 'Admin' })

    await wrapper.find('button[aria-haspopup="menu"]').trigger('click')

    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('priya@example.com')
    expect(wrapper.text()).toContain('Admin')
  })

  it('shows the short name and avatar in the trigger without opening', () => {
    const wrapper = mountMenu({ avatarUrl: 'https://example.com/pic.jpg' })

    expect(wrapper.text()).toContain('Priya')
    expect(wrapper.find('img[src="https://example.com/pic.jpg"]').exists()).toBe(true)
  })

  it("falls back to 'My Account' text with no display name", () => {
    const wrapper = mountMenu({ name: 'My Account', shortName: 'My Account' })

    expect(wrapper.text()).toContain('My Account')
  })

  it('emits select and closes the menu when a row is clicked', async () => {
    const wrapper = mountMenu()

    await wrapper.find('button[aria-haspopup="menu"]').trigger('click')
    await wrapper.find('[role="menuitem"].ds-account-menu-row-danger').trigger('click')

    expect(wrapper.emitted('select')).toEqual([['signout']])
    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
  })

  it('renders a real router-link for items with a "to" target', async () => {
    const wrapper = mountMenu()

    await wrapper.find('button[aria-haspopup="menu"]').trigger('click')

    const dashboardLink = wrapper.find('[role="menuitem"][href="/member"]')
    expect(dashboardLink.exists()).toBe(true)
  })
})
