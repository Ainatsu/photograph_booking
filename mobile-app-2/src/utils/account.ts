import type { AccountContactChannel } from '@/types/auth'

export const MAX_PROFILE_IMAGE_BYTES = 10 * 1024 * 1024

const PROFILE_IMAGE_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'webp'])
const PROFILE_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])

export interface PasswordChangeFields {
  currentPassword: string
  newPassword: string
  confirmPassword: string
}

export interface PasswordChangeErrors {
  currentPassword: string
  newPassword: string
  confirmPassword: string
}

export interface ProfileImageCandidate {
  name: string
  size: number
  type: string
}

export function utf8ByteLength(value: string): number {
  return new TextEncoder().encode(value).length
}

export function validateDisplayName(value: string): string {
  const normalized = value.trim()
  if (!normalized) return '请输入昵称。'
  if (normalized.length > 100) return '昵称不能超过 100 个字符。'
  return ''
}

export function validateContactTarget(channel: AccountContactChannel, value: string): string {
  const normalized = value.trim()
  if (!normalized) return channel === 'phone' ? '请输入手机号。' : '请输入邮箱地址。'

  if (channel === 'email') {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized) ? '' : '邮箱格式不正确，请检查后重试。'
  }

  const compact = normalized.replace(/[()\-\s]/g, '')
  return /^\+?\d{8,15}$/.test(compact) ? '' : '请输入 8–15 位手机号，可包含国家或地区代码。'
}

export function validateVerificationCode(value: string): string {
  const normalized = value.trim()
  if (!normalized) return '请输入验证码。'
  if (!/^\d{4,10}$/.test(normalized)) return '验证码应为 4–10 位数字。'
  return ''
}

export function validatePasswordChange(fields: PasswordChangeFields): PasswordChangeErrors {
  const errors: PasswordChangeErrors = {
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  }

  if (!fields.currentPassword) errors.currentPassword = '请输入当前密码。'
  if (!fields.newPassword) errors.newPassword = '请输入新密码。'
  else if (fields.newPassword.length < 8) errors.newPassword = '新密码至少需要 8 个字符。'
  else if (utf8ByteLength(fields.newPassword) > 72) errors.newPassword = '新密码不能超过 72 个 UTF-8 字节。'
  else if (fields.newPassword === fields.currentPassword) errors.newPassword = '新密码不能与当前密码相同。'

  if (!fields.confirmPassword) errors.confirmPassword = '请再次输入新密码。'
  else if (fields.confirmPassword !== fields.newPassword) errors.confirmPassword = '两次输入的新密码不一致。'

  return errors
}

export function validateProfileImage(file: ProfileImageCandidate): string {
  const extension = file.name.split('.').pop()?.toLowerCase() || ''
  if (!PROFILE_IMAGE_EXTENSIONS.has(extension) || (file.type && !PROFILE_IMAGE_TYPES.has(file.type))) {
    return '仅支持 JPG、PNG 或 WebP 图片。'
  }
  if (file.size > MAX_PROFILE_IMAGE_BYTES) return '图片不能超过 10 MB。'
  return ''
}
