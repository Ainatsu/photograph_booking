export type PhotographerApplicationStatus = 'pending' | 'approved' | 'rejected' | string

export interface PhotographerPortfolioReference {
  id?: string | number
  url?: string
  images?: string[]
  media_type?: string
  thumbnail_url?: string | null
  thumbnail_urls?: string[]
  title?: string | null
  description?: string | null
  tag?: string | null
  tags?: string[]
  created_at?: string | null
  [key: string]: unknown
}

export interface PhotographerApplication {
  id: number
  user_id: number
  user_display_name?: string | null
  user_email?: string | null
  user_avatar_url?: string | null
  status: PhotographerApplicationStatus
  profile_intro?: string | null
  location: string
  equipment: string
  styles: string[]
  portfolio_refs: PhotographerPortfolioReference[]
  review_note?: string | null
  reviewed_by?: number | null
  reviewed_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface PhotographerApplicationSubmitPayload {
  profile_intro?: string
  location: string
  equipment: string
  styles: string[]
  portfolio_refs: PhotographerPortfolioReference[]
}

export interface PhotographerApplicationFormFields {
  profileIntro: string
  location: string
  equipment: string
  styles: string[]
}

export interface PhotographerApplicationFormErrors {
  profileIntro: string
  location: string
  equipment: string
  styles: string
  portfolio: string
}

export type PhotographerApplicationUploadProgress = (percent: number) => void
