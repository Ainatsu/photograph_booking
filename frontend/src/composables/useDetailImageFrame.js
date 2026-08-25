import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const getTargetHeightByViewport = (viewportWidth) => {
  if (viewportWidth <= 480) {
    return Math.min(260, Math.max(190, viewportWidth * 0.52))
  }
  if (viewportWidth <= 860) return 300
  return Math.min(390, Math.max(280, viewportWidth * 0.3))
}

export function useDetailImageFrame(maxRatio = 16 / 9, maxFrameHeight = 720) {
  const detailPageRef = ref(null)
  const imageHostRef = ref(null)
  const infoSectionRef = ref(null)
  const pageWidth = ref(0)
  const hostWidth = ref(0)
  const infoHeight = ref(0)
  const viewportWidth = ref(typeof window === 'undefined' ? 1280 : window.innerWidth)
  const viewportHeight = ref(typeof window === 'undefined' ? 800 : window.innerHeight)
  let pageResizeObserver = null
  let hostResizeObserver = null
  let infoResizeObserver = null

  const measurePageWidth = () => {
    if (!detailPageRef.value) return
    pageWidth.value = detailPageRef.value.clientWidth
  }

  const measureHostWidth = () => {
    if (!imageHostRef.value) return
    hostWidth.value = imageHostRef.value.clientWidth
  }

  const measureInfoHeight = () => {
    if (!infoSectionRef.value) return
    infoHeight.value = infoSectionRef.value.offsetHeight
  }

  const scheduleMeasure = () => {
    nextTick(() => {
      measurePageWidth()
      measureHostWidth()
      measureInfoHeight()
      if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
        window.requestAnimationFrame(() => {
          measurePageWidth()
          measureHostWidth()
          measureInfoHeight()
        })
      }
    })
  }

  const updateLayout = () => {
    if (typeof window !== 'undefined') {
      viewportWidth.value = window.innerWidth
      viewportHeight.value = window.innerHeight
    }
    scheduleMeasure()
  }

  const attachPageObserver = () => {
    pageResizeObserver?.disconnect()
    pageResizeObserver = null
    scheduleMeasure()

    if (!detailPageRef.value || typeof ResizeObserver === 'undefined') return
    pageResizeObserver = new ResizeObserver(() => {
      measurePageWidth()
    })
    pageResizeObserver.observe(detailPageRef.value)
  }

  const attachHostObserver = () => {
    hostResizeObserver?.disconnect()
    hostResizeObserver = null
    scheduleMeasure()

    if (!imageHostRef.value || typeof ResizeObserver === 'undefined') return
    hostResizeObserver = new ResizeObserver(([entry]) => {
      hostWidth.value = entry.contentRect.width
    })
    hostResizeObserver.observe(imageHostRef.value)
  }

  const attachInfoObserver = () => {
    infoResizeObserver?.disconnect()
    infoResizeObserver = null
    scheduleMeasure()

    if (!infoSectionRef.value || typeof ResizeObserver === 'undefined') return
    infoResizeObserver = new ResizeObserver(() => {
      measureInfoHeight()
    })
    infoResizeObserver.observe(infoSectionRef.value)
  }

  const getDesktopMaxImageWidth = () => {
    const pageEl = detailPageRef.value
    const infoEl = infoSectionRef.value
    const layoutEl = infoEl?.parentElement
    if (!pageEl || !infoEl || !layoutEl) return 0

    const pageStyle = window.getComputedStyle(pageEl)
    const layoutStyle = window.getComputedStyle(layoutEl)
    const pageContentWidth = (pageWidth.value || pageEl.clientWidth)
      - Number.parseFloat(pageStyle.paddingLeft || '0')
      - Number.parseFloat(pageStyle.paddingRight || '0')
    const layoutGutter = Number.parseFloat(layoutStyle.paddingLeft || '0')
    const layoutGap = Number.parseFloat(layoutStyle.columnGap || layoutStyle.gap || '0')
    const infoWidth = infoEl.offsetWidth
    return Math.max(0, pageContentWidth - layoutGutter - layoutGap - infoWidth - 4)
  }

  const getPreferredDesktopHeight = () => {
    const pageEl = detailPageRef.value
    if (!pageEl) {
      return Math.min(maxFrameHeight, Math.max(280, viewportHeight.value - 76 - 40))
    }

    const pageStyle = window.getComputedStyle(pageEl)
    const pageContentHeight = pageEl.clientHeight
      - Number.parseFloat(pageStyle.paddingTop || '0')
      - Number.parseFloat(pageStyle.paddingBottom || '0')
    return Math.min(maxFrameHeight, Math.max(280, pageContentHeight))
  }

  const getTargetHeight = () => {
    return viewportWidth.value > 860 ? getPreferredDesktopHeight() : getTargetHeightByViewport(viewportWidth.value)
  }

  const frameHeight = computed(() => {
    if (viewportWidth.value > 860) return getPreferredDesktopHeight()

    const targetHeight = getTargetHeightByViewport(viewportWidth.value)
    if (!hostWidth.value) return targetHeight
    return Math.min(targetHeight, hostWidth.value / maxRatio)
  })

  const getFrameMetrics = (ratio) => {
    const safeRatio = Number.isFinite(Number(ratio)) && Number(ratio) > 0 ? Number(ratio) : 1
    const currentHostWidth = imageHostRef.value?.clientWidth || hostWidth.value
    const desktopMaxImageHeight = getDesktopMaxImageWidth() / safeRatio
    const targetHeight = getTargetHeight()
    const measuredHeight = viewportWidth.value > 860
      ? Math.min(targetHeight, desktopMaxImageHeight || targetHeight)
      : currentHostWidth
        ? Math.min(targetHeight, currentHostWidth / maxRatio)
        : frameHeight.value
    const height = Math.round(measuredHeight)

    return {
      width: Math.round(height * safeRatio),
      height,
    }
  }

  const getFrameStyle = (ratio) => {
    const { width, height } = getFrameMetrics(ratio)
    return {
      width: `${width}px`,
      height: `${height}px`,
    }
  }

  const getLayoutStyle = (ratio) => {
    if (viewportWidth.value <= 860) return {}
    const { height } = getFrameMetrics(ratio)
    return {
      height: `${height}px`,
    }
  }

  onMounted(() => {
    if (typeof window !== 'undefined') {
      window.addEventListener('resize', updateLayout)
    }
    attachPageObserver()
    attachHostObserver()
    attachInfoObserver()
  })

  watch(detailPageRef, attachPageObserver, { flush: 'post' })
  watch(imageHostRef, attachHostObserver, { flush: 'post' })
  watch(infoSectionRef, attachInfoObserver, { flush: 'post' })

  onUnmounted(() => {
    pageResizeObserver?.disconnect()
    hostResizeObserver?.disconnect()
    infoResizeObserver?.disconnect()
    if (typeof window !== 'undefined') {
      window.removeEventListener('resize', updateLayout)
    }
  })

  return { detailPageRef, imageHostRef, infoSectionRef, getFrameStyle, getLayoutStyle }
}
