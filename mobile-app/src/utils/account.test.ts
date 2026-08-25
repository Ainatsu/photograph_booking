import { describe, expect, it } from 'vitest'
import {
  MAX_PROFILE_IMAGE_BYTES,
  utf8ByteLength,
  validateContactTarget,
  validateDisplayName,
  validatePasswordChange,
  validateProfileImage,
  validateVerificationCode,
} from './account'

describe('account settings validation', () => {
  it('validates editable profile and contact fields', () => {
    expect(validateDisplayName('')).toContain('昵称')
    expect(validateDisplayName('光影记录者')).toBe('')
    expect(validateContactTarget('email', 'artist@example.com')).toBe('')
    expect(validateContactTarget('email', 'artist.example.com')).toContain('邮箱格式')
    expect(validateContactTarget('phone', '+852 9123 4567')).toBe('')
    expect(validateContactTarget('phone', '123')).toContain('8–15')
  })

  it('matches the backend password length and confirmation rules', () => {
    expect(utf8ByteLength('摄影师123456')).toBeGreaterThan('摄影师123456'.length)
    expect(validatePasswordChange({
      currentPassword: 'old-password',
      newPassword: 'new-password',
      confirmPassword: 'new-password',
    })).toEqual({ currentPassword: '', newPassword: '', confirmPassword: '' })

    const tooLong = '测'.repeat(25)
    expect(validatePasswordChange({
      currentPassword: 'old-password',
      newPassword: tooLong,
      confirmPassword: tooLong,
    }).newPassword).toContain('72')
  })

  it('validates one-time codes and profile image limits', () => {
    expect(validateVerificationCode('123456')).toBe('')
    expect(validateVerificationCode('12ab')).toContain('数字')
    expect(validateProfileImage({ name: 'avatar.webp', type: 'image/webp', size: 1024 })).toBe('')
    expect(validateProfileImage({ name: 'avatar.gif', type: 'image/gif', size: 1024 })).toContain('JPG')
    expect(validateProfileImage({
      name: 'cover.jpg',
      type: 'image/jpeg',
      size: MAX_PROFILE_IMAGE_BYTES + 1,
    })).toContain('10 MB')
  })
})
