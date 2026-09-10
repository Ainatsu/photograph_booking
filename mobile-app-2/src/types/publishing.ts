import type { PackageOffer, PhotographerProfile, ProjectBrief, WorkItem } from '@/types/discovery'

export type PublishResourceType = 'project' | 'work' | 'package'
export type UploadProgressHandler = (percent: number) => void

export interface ProjectCreatePayload {
  title: string
  description: string
  category: string
  style_tags: string[]
  city: string
  location_text?: string | null
  location_name?: string | null
  location_address?: string | null
  location_latitude?: number | null
  location_longitude?: number | null
  location_place_id?: string | null
  location_provider?: string | null
  coordinate_system?: string | null
  location_precision?: string | null
  shoot_date_start?: string | null
  shoot_date_end?: string | null
  duration_minutes?: number | null
  budget_min?: number | null
  budget_max?: number | null
  deliverables?: string | null
  reference_images: string[]
  visibility: 'public' | 'invite_only'
  expires_at?: string | null
  publish: boolean
}

export type ProjectUpdatePayload = Omit<ProjectCreatePayload, 'publish'>

export interface WorkPublishMetadata {
  title: string
  tags: string[]
  description: string
}

export interface WorkPublishResponse {
  message: string
  work: WorkItem
}

export interface PackageCreatePayload {
  name: string
  price: number
  duration: number
  description?: string
  includes: string[]
  styles: string[]
  city?: string
  service_location?: string
  samples: string[]
  sample_thumbnails: string[]
  original_image_count?: number
  retouched_image_count?: number
  image_count?: number
  delivery_formats: string[]
  included_revision_count: number
  delivery_days: number
  commercial_license: boolean
  terms_rules?: string | null
  is_active: boolean
  payment_mode: 'full' | 'deposit_balance'
  deposit_rate: number
  fulfillment_mode: 'single_delivery'
}

export interface PackagePublishResponse {
  profile: PhotographerProfile
  package: PackageOffer | null
}

export type ProjectPublishResponse = ProjectBrief
