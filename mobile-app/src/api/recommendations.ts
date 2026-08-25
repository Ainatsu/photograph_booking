import api from './client'

export interface RecommendationEvent {
  event_type: string
  target_type: string
  target_id: number | string
  position?: number
  scene?: string
  session_id?: string
  owner_user_id?: number
  recommendation_id?: string
  algorithm_version?: string
  candidate_source?: string
  metadata?: Record<string, unknown>
}

export async function trackRecommendationEvents(events: RecommendationEvent[]): Promise<void> {
  try {
    await api.post('/recommendations/events/batch', { events }, { skipErrorHandler: true } as any)
  } catch {
    // Silently fail - events are non-critical
  }
}

export async function getRecommendedProjects(params: Record<string, unknown> = {}): Promise<any[]> {
  const { data } = await api.get('/recommendations/projects', { params })
  return data.items || []
}

export interface PackageRecommendationQuery {
  city?: string
  styles?: string[] | string
  budget_min?: number
  budget_max?: number
  budget_strict?: boolean
  date_strict?: boolean
  shoot_date?: string
  time_start?: string
  time_end?: string
  duration_minutes?: number
  location_text?: string
  latitude?: number
  longitude?: number
  max_distance_km?: number
  require_exact_availability?: boolean
  sort_mode?: 'best_match' | 'nearest' | 'lowest_price' | 'earliest_available'
  cursor?: string
  limit?: number
  session_id?: string
}

export interface RecommendationSlot {
  start_at: string
  end_at: string
  label: string
}

export interface BookablePackageRecommendation {
  id: string
  package_name: string
  price: number
  duration: number
  styles: string[]
  samples: string[]
  photographer_id: number
  photographer_name?: string
  photographer_avatar?: string
  distance_km?: number | null
  distance_label: string
  distance_confidence: 'exact' | 'unknown' | string
  availability?: {
    date: string
    timezone: string
    matching_slots: RecommendationSlot[]
    snapshot_expires_at: string
  } | null
  match: Record<string, number>
  recommendation_reasons: string[]
  warnings: string[]
}

export interface PackageRecommendationResponse {
  recommendation_id: string
  algorithm_version: string
  next_cursor?: string | null
  fallback_level: number
  relaxations: Array<{ code: string; label: string; from?: unknown; to?: unknown; range_days?: number }>
  no_result: boolean
  feature_enabled: boolean
  observability: Record<string, number | string>
  items: BookablePackageRecommendation[]
}

export async function getRecommendedPackages(params: PackageRecommendationQuery = {}): Promise<PackageRecommendationResponse> {
  const normalized = { ...params, styles: Array.isArray(params.styles) ? params.styles.join(',') : params.styles }
  const { data } = await api.get('/recommendations/packages', { params: normalized })
  return data
}
