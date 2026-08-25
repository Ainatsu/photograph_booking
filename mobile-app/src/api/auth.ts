import api from './client'
import type {
  AccountContactChannel,
  ApiMessage,
  PasswordChangePayload,
  RegisterPayload,
  UserProfile,
  UserProfileUpdatePayload,
  UsernameAvailability,
  VerificationChallenge,
  VerificationConfirmation,
} from '@/types/auth'

export async function loginAccount(identifier: string, password: string): Promise<string> {
  const form = new URLSearchParams()
  form.set('username', identifier.trim())
  form.set('password', password)
  const { data } = await api.post<{ access_token: string }>('/users/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return data.access_token
}

export async function registerAccount(payload: RegisterPayload): Promise<UserProfile> {
  const { data } = await api.post<UserProfile>('/users/register', payload)
  return data
}

export async function getCurrentUser(): Promise<UserProfile> {
  const { data } = await api.get<UserProfile>('/users/me')
  return data
}

export async function checkUsername(username: string): Promise<UsernameAvailability> {
  const { data } = await api.get<UsernameAvailability>('/users/username-availability', {
    params: { username },
  })
  return data
}

export async function updateCurrentUser(payload: UserProfileUpdatePayload): Promise<UserProfile> {
  const { data } = await api.patch<UserProfile>('/users/me', payload)
  return data
}

async function uploadProfileImage(path: 'avatar' | 'background', file: File): Promise<UserProfile> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<UserProfile>(`/users/me/${path}`, form)
  return data
}

export function uploadCurrentUserAvatar(file: File): Promise<UserProfile> {
  return uploadProfileImage('avatar', file)
}

export function uploadCurrentUserBackground(file: File): Promise<UserProfile> {
  return uploadProfileImage('background', file)
}

export async function requestContactBinding(
  channel: AccountContactChannel,
  target: string,
): Promise<VerificationChallenge> {
  const { data } = await api.post<VerificationChallenge>(`/users/me/${channel}/request`, { target })
  return data
}

export async function confirmVerificationCode(
  challengeId: string,
  code: string,
): Promise<VerificationConfirmation> {
  const { data } = await api.post<VerificationConfirmation>('/auth/verifications/confirm', {
    challenge_id: challengeId,
    code,
  })
  return data
}

export async function confirmContactBinding(
  channel: AccountContactChannel,
  verificationToken: string,
): Promise<UserProfile> {
  const { data } = await api.post<UserProfile>(`/users/me/${channel}/confirm`, {
    verification_token: verificationToken,
  })
  return data
}

export async function changeCurrentPassword(payload: PasswordChangePayload): Promise<ApiMessage> {
  const { data } = await api.post<ApiMessage>('/users/me/change-password', payload)
  return data
}

export async function logoutAllDevices(): Promise<ApiMessage> {
  const { data } = await api.post<ApiMessage>('/users/me/logout-all')
  return data
}
