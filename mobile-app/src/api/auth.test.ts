import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}))

vi.mock('./client', () => ({ default: api }))

import {
  changeCurrentPassword,
  confirmContactBinding,
  confirmVerificationCode,
  logoutAllDevices,
  requestContactBinding,
  updateCurrentUser,
  uploadCurrentUserAvatar,
} from './auth'

describe('account API contract', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('updates profile fields through the current-user endpoint', async () => {
    const profile = { id: 1, display_name: '光影记录者' }
    api.patch.mockResolvedValue({ data: profile })

    await expect(updateCurrentUser({
      display_name: '光影记录者',
      bio: '记录真实故事',
      show_email_on_profile: true,
    })).resolves.toBe(profile)
    expect(api.patch).toHaveBeenCalledWith('/users/me', {
      display_name: '光影记录者',
      bio: '记录真实故事',
      show_email_on_profile: true,
    })
  })

  it('keeps the contact binding two-step verification contract intact', async () => {
    api.post
      .mockResolvedValueOnce({ data: { challenge_id: 'challenge-1', masked_target: 'ar***@example.com', expires_in: 300 } })
      .mockResolvedValueOnce({ data: { verification_token: 'verification-token', expires_in: 600 } })
      .mockResolvedValueOnce({ data: { id: 1, display_name: '光影记录者', email: 'artist@example.com' } })

    const challenge = await requestContactBinding('email', 'artist@example.com')
    const verification = await confirmVerificationCode(challenge.challenge_id, '123456')
    await confirmContactBinding('email', verification.verification_token)

    expect(api.post).toHaveBeenNthCalledWith(1, '/users/me/email/request', { target: 'artist@example.com' })
    expect(api.post).toHaveBeenNthCalledWith(2, '/auth/verifications/confirm', {
      challenge_id: 'challenge-1',
      code: '123456',
    })
    expect(api.post).toHaveBeenNthCalledWith(3, '/users/me/email/confirm', {
      verification_token: 'verification-token',
    })
  })

  it('uses multipart uploads and the security endpoints without reshaping payloads', async () => {
    api.post.mockResolvedValue({ data: { message: 'ok' } })
    const file = new File(['avatar'], 'avatar.jpg', { type: 'image/jpeg' })

    await uploadCurrentUserAvatar(file)
    const uploadPayload = api.post.mock.calls[0][1] as FormData
    expect(api.post.mock.calls[0][0]).toBe('/users/me/avatar')
    expect(uploadPayload.get('file')).toBe(file)

    await changeCurrentPassword({ current_password: 'old-password', new_password: 'new-password' })
    expect(api.post).toHaveBeenNthCalledWith(2, '/users/me/change-password', {
      current_password: 'old-password',
      new_password: 'new-password',
    })

    await logoutAllDevices()
    expect(api.post).toHaveBeenNthCalledWith(3, '/users/me/logout-all')
  })
})
