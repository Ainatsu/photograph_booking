/**
 * Home.spec.js — Home 页面组件测试
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import Home from '../../views/Home.vue'

describe('Home', () => {
  it('renders page title', () => {
    const wrapper = mount(Home)
    expect(wrapper.text()).toContain('好拍档')
  })

  it('renders subtitle', () => {
    const wrapper = mount(Home)
    expect(wrapper.text()).toContain('发现风格契合的摄影师')
  })

  it('has correct CSS class', () => {
    const wrapper = mount(Home)
    expect(wrapper.find('.home').exists()).toBe(true)
  })

  it('renders h1 heading', () => {
    const wrapper = mount(Home)
    const h1 = wrapper.find('h1')
    expect(h1.exists()).toBe(true)
    expect(h1.text()).toBe('好拍档')
  })

  it('renders p tag for description', () => {
    const wrapper = mount(Home)
    const p = wrapper.find('p')
    expect(p.exists()).toBe(true)
  })
})
