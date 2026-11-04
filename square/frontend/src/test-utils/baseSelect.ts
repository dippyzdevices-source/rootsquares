import { nextTick } from 'vue'
// Test helpers for the custom BaseSelect (a button + listbox, not a native <select>).
// `root` is a VueWrapper or a DOMWrapper(document.body) for teleported modals.
interface Findable {
  findAll: (selector: string) => { element: Element; trigger: (e: string) => Promise<void>; text: () => string }[]
}

export async function chooseOption(root: Findable, value: string, nth = 0) {
  const button = root.findAll('.base-select-button')[nth]
  if (!button) throw new Error(`No BaseSelect #${nth} found`)
  const container = button.element.closest('.base-select') as HTMLElement
  if (!container.querySelector('.base-select-menu')) await button.trigger('click')
  const option = Array.from(container.querySelectorAll<HTMLElement>('.base-select-option')).find(
    (o) => o.getAttribute('data-value') === value,
  )
  if (!option) throw new Error(`No option "${value}" in BaseSelect #${nth}`)
  option.click()
  await nextTick()
}

export function selectedLabel(root: Findable, nth = 0): string {
  return root.findAll('.base-select-value')[nth]?.text() ?? ''
}

export function optionLabels(root: Findable, nth = 0): string[] {
  const container = root.findAll('.base-select')[nth].element
  return Array.from(container.querySelectorAll('.base-select-option-label')).map((e) => e.textContent ?? '')
}

// BaseMultiSelect: opens the menu if needed and ticks/unticks one option (the menu stays open).
export async function toggleOption(root: Findable, value: string, nth = 0) {
  await chooseOption(root, value, nth)
}
