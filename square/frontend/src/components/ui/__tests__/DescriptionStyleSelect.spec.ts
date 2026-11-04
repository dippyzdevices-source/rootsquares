// Tests for DescriptionStyleSelect (3 cases), e.g. DescriptionStyleSelect; defaults to the site default and emits the chosen style, "" meaning th; shows a validation error from the server.
import { describe, expect, it } from 'vitest'
import { chooseOption, selectedLabel } from '../../../test-utils/baseSelect'
import { mount } from '@vue/test-utils'
import DescriptionStyleSelect from '../DescriptionStyleSelect.vue'

describe('DescriptionStyleSelect', () => {
  it('defaults to the site default and emits the chosen style, "" meaning the default again', async () => {
    const wrapper = mount(DescriptionStyleSelect, { props: { what: 'article', modelValue: '' } })
    expect(selectedLabel(wrapper)).toBe('Site default')
    expect(wrapper.text()).toContain('this article only')

    await chooseOption(wrapper, 'cormorant')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['cormorant'])
    await chooseOption(wrapper, '')
    expect(wrapper.emitted('update:modelValue')?.[1]).toEqual([''])
  })

  it('shows a validation error from the server', () => {
    const wrapper = mount(DescriptionStyleSelect, { props: { what: 'album', modelValue: '', error: 'Must be one of: karla' } })
    expect(wrapper.find('.ds-field-error-text').text()).toBe('Must be one of: karla')
  })
})
