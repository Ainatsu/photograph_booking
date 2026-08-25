import { describe, expect, it } from 'vitest'
import { formatCurrency, formatDuration, formatProjectBudget, getPackageName } from './format'

describe('display formatters', () => {
  it('formats prices and duration for mobile cards', () => {
    expect(formatCurrency(699)).toContain('699')
    expect(formatDuration(120)).toBe('2 小时')
    expect(formatDuration(90)).toBe('1 小时 30 分')
  })

  it('supports both package name fields returned by the APIs', () => {
    expect(getPackageName({ id: '1', price: 1, package_name: '城市写真' })).toBe('城市写真')
    expect(getPackageName({ id: '2', price: 1, name: '婚礼跟拍' })).toBe('婚礼跟拍')
  })

  it('formats bounded project budgets', () => {
    const budget = formatProjectBudget({
      id: 1,
      customer_id: 1,
      title: '测试企划',
      description: '描述',
      category: '人像',
      city: '上海',
      budget_min: 1000,
      budget_max: 1800,
      status: 'open',
      created_at: '2026-07-23T00:00:00Z',
    })
    expect(budget).toContain('1,000')
    expect(budget).toContain('1,800')
  })
})
