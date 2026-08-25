export function formatEngagementTime(value?: string | null, now = new Date()): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''

  const elapsed = Math.max(0, now.getTime() - date.getTime())
  const minutes = Math.floor(elapsed / 60_000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`

  const sameYear = date.getFullYear() === now.getFullYear()
  return new Intl.DateTimeFormat('zh-CN', {
    ...(sameYear ? {} : { year: 'numeric' as const }),
    month: 'short',
    day: 'numeric',
  }).format(date)
}
