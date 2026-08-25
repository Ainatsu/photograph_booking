import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import AppTopBar from './AppTopBar.vue'

function mountBar(props: Record<string, unknown> = {}) {
  return mount(AppTopBar, {
    props,
    slots: {
      center: '<div class="segment-stub">切换栏</div>',
      trailing: '<button class="trailing-stub" type="button">筛选</button>',
    },
    attachTo: document.body,
  })
}

describe('AppTopBar', () => {
  it('把中部插槽渲染在 agent 按钮与搜索按钮之间', () => {
    const wrapper = mountBar()
    const children = Array.from(wrapper.element.children).map((el) => (el as HTMLElement).className)

    expect(children[0]).toContain('icon-action')
    expect(children[1]).toContain('top-bar-center')
    expect(children[2]).toContain('trailing-stub')
    expect(children[3]).toContain('icon-action')
    expect(wrapper.find('.segment-stub').exists()).toBe(true)
    wrapper.unmount()
  })

  it('点击搜索按钮后切换栏变为搜索输入框', async () => {
    const wrapper = mountBar()
    await wrapper.get('button[aria-label="搜索"]').trigger('click')

    expect(wrapper.find('.segment-stub').exists()).toBe(false)
    expect(wrapper.find('.trailing-stub').exists()).toBe(false)
    expect(wrapper.find('input[type="search"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('点击退出按钮恢复切换栏并清空关键词', async () => {
    const wrapper = mountBar()
    await wrapper.get('button[aria-label="搜索"]').trigger('click')
    await wrapper.get('input[type="search"]').setValue('婚纱')
    await wrapper.get('button[aria-label="退出搜索"]').trigger('click')

    expect(wrapper.find('input[type="search"]').exists()).toBe(false)
    expect(wrapper.find('.segment-stub').exists()).toBe(true)

    await wrapper.get('button[aria-label="搜索"]').trigger('click')
    expect(wrapper.get('input[type="search"]').element as HTMLInputElement).toHaveProperty('value', '')
    wrapper.unmount()
  })

  it('点击顶栏之外的区域恢复切换栏', async () => {
    const outside = document.createElement('div')
    document.body.appendChild(outside)
    const wrapper = mountBar()

    await wrapper.get('button[aria-label="搜索"]').trigger('click')
    await nextTick()

    outside.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await nextTick()

    expect(wrapper.find('input[type="search"]').exists()).toBe(false)
    expect(wrapper.find('.segment-stub').exists()).toBe(true)

    outside.remove()
    wrapper.unmount()
  })

  it('点击输入框内部不会退出搜索', async () => {
    const wrapper = mountBar()
    await wrapper.get('button[aria-label="搜索"]').trigger('click')
    await nextTick()

    await wrapper.get('input[type="search"]').trigger('click')
    await nextTick()

    expect(wrapper.find('input[type="search"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('提交搜索时抛出关键词，collapse-on-submit 时收起输入框', async () => {
    const wrapper = mountBar({ collapseOnSubmit: true })
    await wrapper.get('button[aria-label="搜索"]').trigger('click')
    await wrapper.get('input[type="search"]').setValue('  外景写真  ')
    await wrapper.get('input[type="search"]').trigger('keydown.enter')

    expect(wrapper.emitted('search')).toEqual([['外景写真']])
    expect(wrapper.find('input[type="search"]').exists()).toBe(false)
    expect(wrapper.find('.segment-stub').exists()).toBe(true)
    wrapper.unmount()
  })

  it('未提供中部插槽时保持原有的左右布局', () => {
    const wrapper = mount(AppTopBar, { attachTo: document.body })

    expect(wrapper.classes()).not.toContain('has-center')
    expect(wrapper.find('button[aria-label="AI 助手"]').exists()).toBe(true)
    expect(wrapper.find('button[aria-label="搜索"]').exists()).toBe(true)
    wrapper.unmount()
  })
})
