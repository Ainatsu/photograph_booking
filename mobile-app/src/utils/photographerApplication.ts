import type {
  PhotographerApplication,
  PhotographerApplicationFormErrors,
  PhotographerApplicationFormFields,
  PhotographerPortfolioReference,
} from '@/types/photographerApplication'

export const MAX_APPLICATION_PORTFOLIO_ITEMS = 18

export function emptyPhotographerApplicationErrors(): PhotographerApplicationFormErrors {
  return {
    profileIntro: '',
    location: '',
    equipment: '',
    styles: '',
    portfolio: '',
  }
}

export function validateApplicationIntro(value: string): string {
  const normalized = value.trim()
  if (!normalized) return '请介绍你的拍摄经验、擅长题材或服务方式。'
  if (normalized.length > 1000) return '摄影师介绍不能超过 1000 个字符。'
  return ''
}

export function validateApplicationLocation(value: string): string {
  const normalized = value.trim()
  if (!normalized) return '请填写主要服务地区。'
  if (normalized.length > 255) return '服务地区不能超过 255 个字符。'
  return ''
}

export function validateApplicationEquipment(value: string): string {
  const normalized = value.trim()
  if (!normalized) return '请填写常用机身、镜头或灯光设备。'
  if (normalized.length > 500) return '设备信息不能超过 500 个字符。'
  return ''
}

export function validateApplicationStyles(styles: string[]): string {
  if (!styles.length) return '请至少添加一个擅长风格。'
  if (styles.length > 12) return '最多添加 12 个风格标签。'
  return ''
}

export function validateApplicationPortfolio(count: number): string {
  if (count < 1) return '请至少提交一个代表作品。'
  if (count > MAX_APPLICATION_PORTFOLIO_ITEMS) {
    return `代表作品最多保留 ${MAX_APPLICATION_PORTFOLIO_ITEMS} 个。`
  }
  return ''
}

export function validatePhotographerApplication(
  fields: PhotographerApplicationFormFields,
  portfolioCount: number,
): PhotographerApplicationFormErrors {
  return {
    profileIntro: validateApplicationIntro(fields.profileIntro),
    location: validateApplicationLocation(fields.location),
    equipment: validateApplicationEquipment(fields.equipment),
    styles: validateApplicationStyles(fields.styles),
    portfolio: validateApplicationPortfolio(portfolioCount),
  }
}

export function hydratePhotographerApplicationFields(
  application: PhotographerApplication | null,
): PhotographerApplicationFormFields {
  return {
    profileIntro: application?.profile_intro || '',
    location: application?.location || '',
    equipment: application?.equipment || '',
    styles: Array.isArray(application?.styles) ? [...application.styles] : [],
  }
}

export function normalizePortfolioReferences(value: unknown): PhotographerPortfolioReference[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is PhotographerPortfolioReference => Boolean(item && typeof item === 'object'))
}

export function photographerApplicationStatusLabel(status?: string | null): string {
  return ({
    pending: '审核中',
    approved: '已通过',
    rejected: '未通过',
  }[status || ''] || (status ? '状态待确认' : '未提交'))
}

export function photographerApplicationSummary(
  status?: string | null,
  isPhotographer = false,
): string {
  if (isPhotographer || status === 'approved') return '认证已通过，可查看认证状态'
  if (status === 'pending') return '资料审核中，查看进度或更新材料'
  if (status === 'rejected') return '申请未通过，修改材料后重新提交'
  return '提交资料与代表作品，开通摄影师能力'
}

export function portfolioReferencePreview(reference: PhotographerPortfolioReference): string {
  if (typeof reference.thumbnail_url === 'string' && reference.thumbnail_url) return reference.thumbnail_url
  const thumbnail = reference.thumbnail_urls?.find((item) => typeof item === 'string' && item)
  if (thumbnail) return thumbnail
  const image = reference.images?.find((item) => typeof item === 'string' && item)
  if (image) return image
  return typeof reference.url === 'string' ? reference.url : ''
}
