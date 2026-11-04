// Tests for BannerImage (5 cases), e.g. BannerImage; renders a matte background layer plus the real image at object-fit: co; shows the placeholder when there is no src.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BannerImage from '../BannerImage.vue'

describe('BannerImage', () => {
  it('renders a matte background layer plus the real image at object-fit: contain', () => {
    const wrapper = mount(BannerImage, { props: { src: 'https://x/photo.jpg', alt: 'A photo' } })

    expect(wrapper.find('.ds-banner-bg').exists()).toBe(true)

    const fg = wrapper.find('img.ds-banner-fg')
    expect(fg.attributes('src')).toBe('https://x/photo.jpg')
    expect(fg.attributes('alt')).toBe('A photo')
  })

  it('shows the placeholder when there is no src', () => {
    const wrapper = mount(BannerImage, { props: { src: null, alt: 'A photo' } })

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.ds-placeholder').exists()).toBe(true)
  })

  it('falls back to the placeholder if the image fails to load', async () => {
    const wrapper = mount(BannerImage, { props: { src: 'https://x/broken.jpg', alt: 'A photo' } })

    await wrapper.find('img').trigger('error')

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.ds-placeholder').exists()).toBe(true)
  })

  it('recovers once a new, different src is provided after a failure', async () => {
    const wrapper = mount(BannerImage, { props: { src: 'https://x/broken.jpg', alt: 'A photo' } })
    await wrapper.find('img').trigger('error')
    expect(wrapper.find('.ds-placeholder').exists()).toBe(true)

    await wrapper.setProps({ src: 'https://x/good.jpg' })

    expect(wrapper.find('.ds-placeholder').exists()).toBe(false)
    expect(wrapper.find('img').attributes('src')).toBe('https://x/good.jpg')
  })
})
