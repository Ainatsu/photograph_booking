import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}))

vi.mock('./client', () => ({ default: api }))

import {
  getMyPhotographerApplication,
  submitMyPhotographerApplication,
  uploadPhotographerApplicationWorks,
} from './photographerApplications'

describe('photographer application API contract', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads and submits the current user application without reshaping fields', async () => {
    const application = { id: 7, user_id: 3, status: 'pending', location: '成都', equipment: 'Sony A7 IV', styles: ['人像'], portfolio_refs: [] }
    api.get.mockResolvedValue({ data: application })
    api.post.mockResolvedValue({ data: application })

    await expect(getMyPhotographerApplication()).resolves.toBe(application)
    expect(api.get).toHaveBeenCalledWith('/photographer-applications/me')

    const payload = {
      profile_intro: '专注自然光人像',
      location: '成都',
      equipment: 'Sony A7 IV',
      styles: ['人像'],
      portfolio_refs: [{ id: 'work-1', url: '/static/work-1.jpg' }],
    }
    await expect(submitMyPhotographerApplication(payload)).resolves.toBe(application)
    expect(api.post).toHaveBeenCalledWith('/photographer-applications/me', payload)
  })

  it('uploads each representative image with metadata and aggregate progress', async () => {
    const files = [
      new File(['first'], '城市人像.jpg', { type: 'image/jpeg' }),
      new File(['second'], '夜景.png', { type: 'image/png' }),
    ]
    const progress: number[] = []
    api.post
      .mockImplementationOnce(async (_url, _form, config) => {
        config.onUploadProgress?.({ loaded: 1, total: 2 })
        return { data: { work: { id: 'work-1', url: '/static/work-1.jpg' } } }
      })
      .mockImplementationOnce(async (_url, _form, config) => {
        config.onUploadProgress?.({ loaded: 2, total: 2 })
        return { data: { work: { id: 'work-2', url: '/static/work-2.jpg' } } }
      })

    await expect(uploadPhotographerApplicationWorks(
      files,
      { description: '申请介绍', tags: ['人像', '夜景'] },
      (value) => progress.push(value),
    )).resolves.toEqual([
      { id: 'work-1', url: '/static/work-1.jpg' },
      { id: 'work-2', url: '/static/work-2.jpg' },
    ])

    const firstForm = api.post.mock.calls[0][1] as FormData
    expect(api.post.mock.calls[0][0]).toBe('/photographers/portfolio/upload')
    expect(firstForm.get('file')).toBe(files[0])
    expect(firstForm.get('title')).toBe('城市人像')
    expect(firstForm.get('description')).toBe('申请介绍')
    expect(firstForm.get('tag')).toBe('人像,夜景')
    expect(progress.at(-1)).toBe(100)
  })
})
