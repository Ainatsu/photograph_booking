import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ImageGenerationCard from './ImageGenerationCard.vue'
import { getImageGeneration, regenerateImageGeneration, retryImageGeneration } from '@/api/ai'

vi.mock('@/api/ai', () => ({
  getImageGeneration: vi.fn(),
  retryImageGeneration: vi.fn(),
  regenerateImageGeneration: vi.fn(),
  cancelImageGeneration: vi.fn(),
}))

const reference = { job_id: 12, mode: 'text_to_image', status: 'queued' }
const completedJob = {
  job_id: 12,
  task_id: 'task-12',
  mode: 'text_to_image',
  status: 'completed',
  stage: 'completed',
  progress: { completed: 1, total: 1 },
  source_images: [],
  result_images: [{ id: 1, storage_url: '/static/result.jpg', thumbnail_url: '/static/thumb.jpg', mime_type: 'image/jpeg', position: 0 }],
  parameters: { aspect_ratio: '3:4', quality: 'standard' },
  can_retry: false,
  can_cancel: false,
}

describe('ImageGenerationCard', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.mocked(getImageGeneration).mockReset()
    vi.mocked(retryImageGeneration).mockReset()
    vi.mocked(regenerateImageGeneration).mockReset()
  })

  it('loads a completed job and does not keep polling a terminal state', async () => {
    vi.mocked(getImageGeneration).mockResolvedValue(completedJob as any)
    const wrapper = mount(ImageGenerationCard, { props: { reference, prompt: '黄昏海边人像' } })
    await flushPromises()

    expect(wrapper.text()).toContain('已完成')
    expect(wrapper.get('.result img').attributes('alt')).toBe('AI 生成结果 1')

    await vi.advanceTimersByTimeAsync(4000)
    expect(getImageGeneration).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('retries a failed job and resumes its active state', async () => {
    const failed = { ...completedJob, status: 'failed', stage: 'failed', result_images: [], can_retry: true }
    vi.mocked(getImageGeneration).mockResolvedValue(failed as any)
    vi.mocked(retryImageGeneration).mockResolvedValue({ ...failed, status: 'queued', stage: 'queued', can_retry: false, can_cancel: true } as any)
    const wrapper = mount(ImageGenerationCard, { props: { reference: { ...reference, status: 'failed' } } })
    await flushPromises()

    await wrapper.get('footer .action').trigger('click')
    await flushPromises()

    expect(retryImageGeneration).toHaveBeenCalledWith(12)
    expect(wrapper.text()).toContain('等待生成')
    wrapper.unmount()
  })

  it('creates a new job when regenerating a completed result', async () => {
    vi.mocked(getImageGeneration).mockResolvedValue(completedJob as any)
    vi.mocked(regenerateImageGeneration).mockResolvedValue({ ...completedJob, job_id: 13, status: 'queued', stage: 'queued', result_images: [] } as any)
    const wrapper = mount(ImageGenerationCard, { props: { reference, prompt: '黄昏海边人像' } })
    await flushPromises()

    const regenerateButton = wrapper.findAll('footer .action').find((button) => button.text().includes('重新生成'))
    await regenerateButton!.trigger('click')
    await flushPromises()

    expect(regenerateImageGeneration).toHaveBeenCalledWith(12)
    expect(wrapper.text()).toContain('等待生成')
    wrapper.unmount()
  })
})
