/**
 * counter.spec.js — Pinia Store 单元测试
 * 测试：状态管理、计算属性、方法
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useCounterStore } from '../counter'

describe('Counter Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should initialize with count 0', () => {
    const store = useCounterStore()
    expect(store.count).toBe(0)
  })

  it('should compute doubleCount correctly', () => {
    const store = useCounterStore()
    store.count = 3
    expect(store.doubleCount).toBe(6)
  })

  it('should increment count', () => {
    const store = useCounterStore()
    store.increment()
    expect(store.count).toBe(1)
    store.increment()
    expect(store.count).toBe(2)
  })

  it('should recompute doubleCount after increment', () => {
    const store = useCounterStore()
    store.increment() // count = 1
    store.increment() // count = 2
    expect(store.doubleCount).toBe(4)
  })

  it('should handle negative count', () => {
    const store = useCounterStore()
    store.count = -5
    expect(store.doubleCount).toBe(-10)
  })

  it('should handle zero correctly', () => {
    const store = useCounterStore()
    store.count = 0
    expect(store.doubleCount).toBe(0)
  })

  it('should handle large numbers', () => {
    const store = useCounterStore()
    store.count = 1000000
    expect(store.doubleCount).toBe(2000000)
  })
})
