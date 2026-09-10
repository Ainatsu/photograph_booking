export type InspirationStatus = 'draft' | 'saved' | 'archived'
export type InspirationGenerationState = 'queued' | 'generating' | 'partial' | 'completed' | 'failed' | 'cancelled'
export type InspirationBlockType = 'paragraph' | 'heading' | 'quote' | 'list' | 'image'

export interface InspirationBlock {
  type: InspirationBlockType
  text?: string | null
  url?: string | null
  thumb_url?: string | null
  alt?: string | null
}

export interface Inspiration {
  id: number
  owner_id: number
  title: string
  summary?: string | null
  content: InspirationBlock[]
  cover_url?: string | null
  tags: string[]
  location_name?: string | null
  location_address?: string | null
  latitude?: number | string | null
  longitude?: number | string | null
  place_id?: string | null
  provider?: string | null
  coordinate_system?: string | null
  location_precision?: string | null
  status: InspirationStatus
  visibility: string
  created_at: string
  updated_at: string
  generation?: InspirationGenerationStatus | null
}

export interface InspirationGenerationStatus {
  status: InspirationGenerationState
  total_images: number
  completed_images: number
  failed_images: number
  can_retry: boolean
  updated_at?: string | null
}

export interface InspirationPayload {
  title: string
  summary?: string | null
  content: InspirationBlock[]
  cover_url?: string | null
  tags: string[]
  location_name?: string | null
  location_address?: string | null
  latitude?: number | null
  longitude?: number | null
  place_id?: string | null
  provider?: string | null
  coordinate_system?: string | null
  location_precision?: string | null
  status: 'draft' | 'saved'
}

export interface InspirationMapPoint {
  key: string
  name: string
  latitude: number
  longitude: number
  count: number
  preview: Array<Pick<Inspiration, 'id' | 'title' | 'cover_url' | 'updated_at'>>
}
