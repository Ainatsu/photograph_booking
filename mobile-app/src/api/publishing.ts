import type { AxiosProgressEvent } from 'axios'
import api from './client'
import { appendPhotographerPackage } from './packages'
import type {
  PackageCreatePayload,
  PackagePublishResponse,
  ProjectCreatePayload,
  ProjectPublishResponse,
  UploadProgressHandler,
  WorkPublishMetadata,
  WorkPublishResponse,
} from '@/types/publishing'

function progressHandler(callback?: UploadProgressHandler) {
  return callback
    ? (event: AxiosProgressEvent) => {
        if (!event.total) return
        callback(Math.min(100, Math.round((event.loaded / event.total) * 100)))
      }
    : undefined
}

export async function uploadProjectImages(
  files: File[],
  onProgress?: UploadProgressHandler,
): Promise<string[]> {
  if (!files.length) return []
  const form = new FormData()
  files.forEach((file) => form.append('files', file))
  const { data } = await api.post<{ urls: string[] }>('/projects/upload-images', form, {
    timeout: 0,
    onUploadProgress: progressHandler(onProgress),
  })
  return data.urls || []
}

export async function createProject(payload: ProjectCreatePayload): Promise<ProjectPublishResponse> {
  const { data } = await api.post<ProjectPublishResponse>('/projects/', payload)
  return data
}

export async function uploadImageWork(
  files: File[],
  metadata: WorkPublishMetadata,
  onProgress?: UploadProgressHandler,
): Promise<WorkPublishResponse> {
  const form = new FormData()
  files.forEach((file) => form.append('files', file))
  form.append('title', metadata.title)
  form.append('tag', metadata.tags.join(','))
  form.append('description', metadata.description)
  const { data } = await api.post<WorkPublishResponse>('/photographers/portfolio/upload', form, {
    timeout: 0,
    onUploadProgress: progressHandler(onProgress),
  })
  return data
}

export async function uploadVideoWork(
  file: File,
  cover: File | null,
  metadata: WorkPublishMetadata,
  onProgress?: UploadProgressHandler,
): Promise<WorkPublishResponse> {
  const form = new FormData()
  form.append('file', file)
  if (cover) form.append('cover', cover)
  form.append('title', metadata.title)
  form.append('tag', metadata.tags.join(','))
  form.append('description', metadata.description)
  form.append('compress', 'true')
  const { data } = await api.post<WorkPublishResponse>('/photographers/video/upload', form, {
    timeout: 0,
    onUploadProgress: progressHandler(onProgress),
  })
  return data
}

export async function uploadPackageSamples(
  files: File[],
  onProgress?: UploadProgressHandler,
): Promise<{ urls: string[]; thumbnailUrls: string[] }> {
  if (!files.length) return { urls: [], thumbnailUrls: [] }
  const form = new FormData()
  files.forEach((file) => form.append('files', file))
  const { data } = await api.post<{ urls: string[]; thumbnail_urls?: string[] }>(
    '/photographers/package-samples/upload',
    form,
    { timeout: 0, onUploadProgress: progressHandler(onProgress) },
  )
  const urls = data.urls || []
  return {
    urls,
    thumbnailUrls: data.thumbnail_urls?.length ? data.thumbnail_urls : urls,
  }
}

export async function createPhotographerPackage(
  userId: number,
  payload: PackageCreatePayload,
): Promise<PackagePublishResponse> {
  return appendPhotographerPackage(userId, payload)
}
