import type { PackageOffer, ProjectBrief } from '@/types/discovery'

const currencyFormatter = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})

export function formatCurrency(value?: number | null): string {
  return currencyFormatter.format(Number(value || 0))
}

export function formatDuration(minutes?: number | null): string {
  if (!minutes) return '时长面议'
  if (minutes < 60) return `${minutes} 分钟`
  if (minutes % 60 === 0) return `${minutes / 60} 小时`
  return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分`
}

export function getPackageName(pkg: PackageOffer): string {
  return pkg.package_name || pkg.name || '摄影方案'
}

export function formatProjectBudget<T extends Pick<ProjectBrief, 'budget_min' | 'budget_max'>>(project: T): string {
  const min = project.budget_min
  const max = project.budget_max
  if (min && max) return `${formatCurrency(min)}–${formatCurrency(max)}`
  if (min) return `${formatCurrency(min)} 起`
  if (max) return `${formatCurrency(max)} 内`
  return '预算面议'
}

export function formatShortDate(value?: string | null): string {
  if (!value) return '时间待沟通'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间待沟通'
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
  }).format(date)
}
