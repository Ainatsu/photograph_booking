const statusTones = {
  pending: 'warning',
  awaiting_customer_payment: 'warning',
  reschedule_requested: 'warning',
  delivered: 'warning',
  confirmed: 'brand',
  in_progress: 'brand',
  received: 'brand',
  reviewed: 'brand',
  completed: 'brand',
  cancelled: 'danger'
}

// 订单快照由后端拼接为「方案标题 - ¥价格/时长分钟」，旧订单可能是自由文本。
const PACKAGE_SNAPSHOT_PATTERN = /^(.*?)\s*-\s*¥\s*([\d,]+(?:\.\d+)?)\s*\/\s*(\d+)\s*分钟$/

export function getOrderStatusTone(status) {
  return statusTones[status] || 'neutral'
}

export function parseOrderPackageSnapshot(snapshot) {
  const text = String(snapshot || '').trim()
  if (!text) return null

  const matched = PACKAGE_SNAPSHOT_PATTERN.exec(text)
  if (!matched) return { title: text, price: '', duration: '' }
  return {
    title: matched[1].trim() || text,
    price: `¥${matched[2]}`,
    duration: `${matched[3]} 分钟`
  }
}
