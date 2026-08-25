export const getFullUrl = (url) => {
  if (!url) return ''
  return url.startsWith('http') ? url : url
}

export const isVideoWork = (work) => work?.media_type === 'video'

export const getVideoSourceUrl = (work) => {
  if (!work) return ''
  return getFullUrl(work.compressed_url || work.url || '')
}

export const getVideoStreamUrl = (work) => {
  const src = getVideoSourceUrl(work)
  if (!src || !src.startsWith('/static/')) return src
  return `/api/v1/photographers/video/stream?url=${encodeURIComponent(src)}`
}

export const getWorkPreviewUrl = (work) => {
  if (!work) return ''
  // 视频作品：使用缩略图
  if (isVideoWork(work)) {
    return getFullUrl(work.thumbnail_url || '')
  }
  const thumbnails = Array.isArray(work.thumbnail_urls) ? work.thumbnail_urls : []
  const images = Array.isArray(work.images) ? work.images : []
  return getFullUrl(thumbnails[0] || work.thumbnail_url || images[0] || work.url)
}

export const getPackagePreviewUrl = (pkg, index = 0) => {
  if (!pkg) return ''
  const thumbnails = Array.isArray(pkg.sample_thumbnails) ? pkg.sample_thumbnails : []
  const samples = Array.isArray(pkg.samples) ? pkg.samples : (pkg.samples ? [pkg.samples] : [])
  return getFullUrl(thumbnails[index] || samples[index] || '')
}

export const getFavoriteWorkPreviewUrl = (item) => getWorkPreviewUrl(item?.work_data)

export const getFavoritePackagePreviewUrl = (item, index = 0) => {
  const data = item?.package_data || item
  return getPackagePreviewUrl(data, index)
}
