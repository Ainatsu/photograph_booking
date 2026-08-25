export interface UserProfile {
  id: number
  username?: string | null
  username_requires_update?: boolean
  email?: string | null
  pending_email?: string | null
  phone?: string | null
  email_verified?: boolean
  phone_verified?: boolean
  show_email_on_profile?: boolean
  display_name: string
  bio?: string | null
  avatar_url?: string | null
  background_url?: string | null
  role: 'customer' | 'photographer' | string
  is_active: boolean
  is_admin?: boolean
  is_banned?: boolean
}

export interface RegisterPayload {
  username: string
  display_name: string
  email?: string
  password: string
  phone_verification_token?: string
}

export interface UsernameAvailability {
  normalized_username: string
  available: boolean
  reason?: string | null
}

export type AccountContactChannel = 'phone' | 'email'

export interface UserProfileUpdatePayload {
  display_name: string
  bio: string
  show_email_on_profile?: boolean
}

export interface PasswordChangePayload {
  current_password: string
  new_password: string
}

export interface VerificationChallenge {
  challenge_id: string
  masked_target: string
  expires_in: number
}

export interface VerificationConfirmation {
  verification_token: string
  expires_in: number
}

export interface ApiMessage {
  message: string
}
