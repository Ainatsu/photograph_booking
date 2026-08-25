import type { PackageOffer, WorkItem } from '@/types/discovery'

const assetBase = (import.meta.env.VITE_ASSET_BASE_URL || '').replace(/\/$/, '')

export function resolveMediaUrl(value?: string | null): string {
  if (!value) return ''
  if (/^(https?:|data:|blob:)/i.test(value)) return value

  const path = value.startsWith('/') ? value : `/${value}`
  return assetBase ? `${assetBase}${path}` : path
}

export function getWorkPreviewUrl(work: WorkItem): string {
  const preview =
    work.thumbnail_url ||
    work.thumbnail_urls?.find(Boolean) ||
    work.images?.find(Boolean) ||
    work.url

  return resolveMediaUrl(preview)
}

export function getWorkMediaUrls(work: WorkItem): string[] {
  const values = work.images?.length ? work.images : [work.url || '']
  return values.filter(Boolean).map(resolveMediaUrl)
}

export function getPackagePreviewUrl(pkg: PackageOffer): string {
  const preview = pkg.sample_thumbnails?.find(Boolean) || pkg.samples?.find(Boolean)
  return resolveMediaUrl(preview)
}
