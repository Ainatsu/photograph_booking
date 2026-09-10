import type { PackageOffer, PhotographerProfile, WorkItem } from '@/types/discovery'
import { isPackageActive } from './package'

/** 常驻地层级分隔符：「中国-四川-成都」「上海市/浦东新区」都按同一套规则拆分。 */
const RESIDENCY_SEPARATORS = /[-－—–/／>＞·、,，|｜]+/
/** 纯中文且以空格分隔时（「中国 四川 成都」）同样按层级处理，避免误拆「Los Angeles」。 */
const CJK_SPACED = /^[一-鿿\s]+$/

/** 常驻地标签：只展示用户填写的最详细一级，例如「中国-四川-成都」→「成都」。 */
export function formatResidencyLabel(location: string | null | undefined): string {
  const raw = String(location || '').trim()
  if (!raw) return ''

  const segments = raw.split(RESIDENCY_SEPARATORS).map((part) => part.trim()).filter(Boolean)
  if (!segments.length) return ''
  if (segments.length > 1) return segments[segments.length - 1]

  const single = segments[0]
  if (!CJK_SPACED.test(single)) return single
  const spaced = single.split(/\s+/).filter(Boolean)
  return spaced[spaced.length - 1] || single
}

/** 主页作品列表：补齐卡片需要的作者信息，并为缺少 id 的历史数据兜底。 */
export function getProfileWorks(profile: PhotographerProfile | null | undefined): WorkItem[] {
  if (!profile) return []
  return (profile.portfolio || []).map((work, index) => ({
    ...work,
    id: work.id || `portfolio-${index}`,
    user_id: profile.user_id,
    user_display_name: profile.user_display_name,
    user_avatar_url: profile.user_avatar_url,
  }))
}

/** 主页方案列表：只保留已上架方案，并补齐卡片需要的摄影师信息。 */
export function getProfilePackages(
  profile: PhotographerProfile | null | undefined,
): PackageOffer[] {
  if (!profile) return []
  return (profile.packages || [])
    .filter(isPackageActive)
    .map((offer, index) => ({
      ...offer,
      id: offer.id || `package-${index}`,
      photographer_id: profile.user_id,
      photographer_name: profile.user_display_name,
      photographer_avatar: profile.user_avatar_url,
      photographer_location: profile.location,
    }))
}
