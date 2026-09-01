const MAX_SOURCE_BYTES = 30 * 1024 * 1024
const TARGET_BYTES = 8 * 1024 * 1024
const HARD_LIMIT_BYTES = 10 * 1024 * 1024
const MAX_DIMENSION = 4096

function loadImage(file: File): Promise<{ image: HTMLImageElement; url: string }> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const image = new Image()
    image.onload = () => resolve({ image, url })
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('无法读取所选图片'))
    }
    image.src = url
  })
}

function canvasToBlob(canvas: HTMLCanvasElement, mimeType: string, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      blob => blob ? resolve(blob) : reject(new Error('图片压缩失败')),
      mimeType,
      quality,
    )
  })
}

export async function compressAIReferenceImage(file: File): Promise<File> {
  if (!file.type.startsWith('image/')) throw new Error('请选择 JPG、PNG 或 WebP 图片')
  if (file.size > MAX_SOURCE_BYTES) throw new Error('原始图片不能超过 30 MiB')

  const { image, url } = await loadImage(file)
  try {
    const scale = Math.min(1, MAX_DIMENSION / Math.max(image.naturalWidth, image.naturalHeight))
    let width = Math.max(1, Math.round(image.naturalWidth * scale))
    let height = Math.max(1, Math.round(image.naturalHeight * scale))
    if (scale === 1 && file.size <= TARGET_BYTES) return file

    const preservesAlpha = file.type === 'image/png' || file.type === 'image/webp'
    const mimeType = preservesAlpha ? 'image/webp' : 'image/jpeg'
    const extension = preservesAlpha ? '.webp' : '.jpg'
    const canvas = document.createElement('canvas')
    const context = canvas.getContext('2d')
    if (!context) throw new Error('当前设备无法处理图片')

    const render = () => {
      canvas.width = width
      canvas.height = height
      if (mimeType === 'image/jpeg') {
        context.fillStyle = '#fff'
        context.fillRect(0, 0, width, height)
      }
      context.drawImage(image, 0, 0, width, height)
    }

    render()
    let quality = 0.86
    let blob = await canvasToBlob(canvas, mimeType, quality)
    while (blob.size > TARGET_BYTES && quality > 0.56) {
      quality = Math.max(0.56, quality - 0.06)
      blob = await canvasToBlob(canvas, mimeType, quality)
    }
    while (blob.size > TARGET_BYTES && Math.max(width, height) > 512) {
      const resizeScale = Math.max(0.5, Math.min(0.9, Math.sqrt(TARGET_BYTES / blob.size) * 0.95))
      width = Math.max(1, Math.round(width * resizeScale))
      height = Math.max(1, Math.round(height * resizeScale))
      render()
      blob = await canvasToBlob(canvas, mimeType, quality)
    }
    if (blob.size > HARD_LIMIT_BYTES) throw new Error('图片压缩后仍超过 10 MiB')

    const stem = file.name.replace(/\.[^.]+$/, '') || 'reference'
    return new File([blob], `${stem}${extension}`, { type: mimeType, lastModified: file.lastModified })
  } finally {
    URL.revokeObjectURL(url)
  }
}
