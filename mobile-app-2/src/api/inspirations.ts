import api from './client'
import type { Inspiration, InspirationMapPoint, InspirationPayload } from '@/types/inspiration'

export async function getInspirations(params: { status?: string; query?: string; skip?: number; limit?: number } = {}): Promise<Inspiration[]> {
  const { data } = await api.get<Inspiration[]>('/inspirations/', { params })
  return data
}

export async function getInspiration(id: number): Promise<Inspiration> {
  const { data } = await api.get<Inspiration>(`/inspirations/${id}`)
  return data
}

export async function retryInspirationGeneration(id: number): Promise<Inspiration> {
  const { data } = await api.post<Inspiration>(`/inspirations/${id}/generation/retry`)
  return data
}

export async function createInspiration(payload: InspirationPayload): Promise<Inspiration> {
  const { data } = await api.post<Inspiration>('/inspirations/', payload)
  return data
}

export async function updateInspiration(id: number, payload: Partial<InspirationPayload>): Promise<Inspiration> {
  const { data } = await api.put<Inspiration>(`/inspirations/${id}`, payload)
  return data
}

export async function archiveInspiration(id: number): Promise<void> {
  await api.delete(`/inspirations/${id}`)
}

export async function getInspirationMap(query?: string): Promise<InspirationMapPoint[]> {
  const { data } = await api.get<{ points: InspirationMapPoint[] }>('/inspirations/map', { params: { query: query || undefined } })
  return data.points
}

export async function uploadInspirationImage(file: File): Promise<{ url: string; thumb_url?: string | null }> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<{ url: string; thumb_url?: string | null }>('/inspirations/upload-images', form, { timeout: 0 })
  return data
}
