import { config } from '@vue/test-utils'

/**
 * 测试全局设置。
 *
 * 1. IonIcon 未在测试里注册，统一 stub 掉，避免"未注册组件"报错。
 * 2. renderStubDefaultSlot 默认是 false —— 那样 stub 会把插槽内容整块吃掉，
 *    页面级测试里 IonPage/IonContent 一 stub 里面的表单就全没了。
 *    打开它，stub 只替换容器本身，内容照常渲染。
 */
config.global.stubs = {
  IonIcon: true,
}
config.global.renderStubDefaultSlot = true
