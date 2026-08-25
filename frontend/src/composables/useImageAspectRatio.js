import { reactive } from 'vue'

/**
 * 图片瀑布流卡片动态裁剪比例
 * 规则: ratio > 4/3 → 4:3  /  ratio < 3/4 → 3:4  /  其余 → 1:1
 * 图片使用 fit="cover" + overflow:hidden 自然居中裁剪
 */
export function useImageAspectRatio() {
  const ratios = reactive({})
  const detailRatioSteps = [9 / 16, 3 / 4, 1, 4 / 3, 16 / 9]

  const preload = (url, key) => {
    if (!url || !key) return
    if (ratios[key] !== undefined) return
    const img = new Image()
    img.onload = () => {
      if (img.naturalWidth && img.naturalHeight) {
        ratios[key] = img.naturalWidth / img.naturalHeight
      }
    }
    img.onerror = () => {
      ratios[key] = 1 // fallback 1:1
    }
    img.src = url
  }

  const getRatio = (key) => {
    const ratio = ratios[key]
    if (ratio === undefined) return '1/1'
    if (ratio > 4 / 3) return '4/3'
    if (ratio < 3 / 4) return '3/4'
    return '1/1'
  }

  const clampRatio = (ratio, minRatio = 9 / 16, maxRatio = 16 / 9) => {
    const safeRatio = Number.isFinite(ratio) && ratio > 0 ? ratio : 1
    return Math.min(maxRatio, Math.max(minRatio, safeRatio))
  }

  const getClampedRatio = (key, minRatio = 9 / 16, maxRatio = 16 / 9) => {
    const ratio = ratios[key]
    if (ratio === undefined) return '1'
    return String(Number(clampRatio(ratio, minRatio, maxRatio).toFixed(4)))
  }

  /**
   * 获取比例，如果尚未预加载则触发懒加载
   * 适用于模板中直接调用
   */
  const getOrPreload = (url, key) => {
    const ratio = ratios[key]
    if (ratio === undefined) {
      preload(url, key)
      return '1/1'
    }
    if (ratio > 4 / 3) return '4/3'
    if (ratio < 3 / 4) return '3/4'
    return '1/1'
  }

  const getClampedOrPreload = (url, key, minRatio = 9 / 16, maxRatio = 16 / 9) => {
    if (!key) return '1'
    const ratio = ratios[key]
    if (ratio === undefined) {
      preload(url, key)
      return '1'
    }
    return getClampedRatio(key, minRatio, maxRatio)
  }

  const getSteppedDetailRatio = (key) => {
    const ratio = ratios[key]
    if (ratio === undefined) return '1'
    const safeRatio = Number.isFinite(ratio) && ratio > 0 ? ratio : 1
    const steppedRatio = detailRatioSteps.reduce((closest, step) => {
      const closestDistance = Math.abs(Math.log(safeRatio / closest))
      const stepDistance = Math.abs(Math.log(safeRatio / step))
      return stepDistance < closestDistance ? step : closest
    }, detailRatioSteps[0])
    return String(Number(steppedRatio.toFixed(4)))
  }

  const getSteppedDetailOrPreload = (url, key) => {
    if (!key) return '1'
    if (ratios[key] === undefined) {
      preload(url, key)
      return '1'
    }
    return getSteppedDetailRatio(key)
  }

  const preloadAll = (list, getUrl, getKey) => {
    if (!list || !list.length) return
    list.forEach((item) => {
      const url = getUrl(item)
      const key = getKey(item)
      preload(url, key)
    })
  }

  return {
    ratios,
    preload,
    getRatio,
    getOrPreload,
    preloadAll,
    getClampedRatio,
    getClampedOrPreload,
    getSteppedDetailRatio,
    getSteppedDetailOrPreload,
  }
}
