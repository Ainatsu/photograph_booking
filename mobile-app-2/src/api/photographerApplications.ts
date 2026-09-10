import type { AxiosProgressEvent } from 'axios'
import api from './client'
import type {
  PhotographerApplication,
  PhotographerApplicationSubmitPayload,
  PhotographerApplicationUploadProgress,
  PhotographerPortfolioReference,
} from '@/types/photographerApplication'

export async function getMyPhotographerApplication(): Promise<PhotographerApplication | null> {
  const { data } = await api.get<PhotographerApplication | null>('/photographer-applications/me')
  return data
}

export async function submitMyPhotographerApplication(
  payload: PhotographerApplicationSubmitPayload,
): Promise<PhotographerApplication> {
  const { data } = await api.post<PhotographerApplication>('/photographer-applications/me', payload)
  return data
}

export async function uploadPhotographerApplicationWorks(
  files: File[],
  metadata: { description: string; tags: string[] },
  onProgress?: PhotographerApplicationUploadProgress,
): Promise<PhotographerPortfolioReference[]> {
  const works: PhotographerPortfolioReference[] = []
  if (!files.length) return works

  for (const [index, file] of files.entries()) {
    const form = new FormData()
    form.append('file', file)
    form.append('title', file.name.replace(/\.[^.]+$/, '') || `认证代表作品 ${index + 1}`)
    form.append('description', metadata.description)
    form.append('tag', metadata.tags.join(','))

    const { data } = await api.post<{ work: PhotographerPortfolioReference }>(
      '/photographers/portfolio/upload',
      form,
      {
        timeout: 0,
        onUploadProgress: onProgress
          ? (event: AxiosProgressEvent) => {
              if (!event.total) return
              const current = Math.min(1, event.loaded / event.total)
              onProgress(Math.round(((index + current) / files.length) * 100))
            }
          : undefined,
      },
    )
    works.push(data.work)
    onProgress?.(Math.round(((index + 1) / files.length) * 100))
  }

  return works
}
