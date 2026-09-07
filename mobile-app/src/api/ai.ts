import api from './client'
import type { AgentTask } from '@/types/agentTask'

// ── Page context types for agent handoff ──

export type AIPageContextResourceType =
  | 'portfolio_item'
  | 'photographer'
  | 'package'
  | 'project'

export interface AIPageContext {
  route_name: string
  route_path: string
  resource_type: AIPageContextResourceType
  resource_id: string
  title: string
  summary?: string
  description?: string
  tags?: string[]
  styles?: string[]
  city?: string
  location?: string
  status?: string
  price?: number
  price_label?: string
  budget_label?: string
  date_label?: string
  duration?: number
  image_count?: number
  owner_user_id?: number
  owner_display_name?: string
  photographer_id?: number
  photographer_name?: string
  package_name?: string
  packages?: Array<Record<string, unknown>>
  portfolio?: Array<Record<string, unknown>>
  applications?: Array<Record<string, unknown>>
  current_object?: {
    media_type?: string
    image_url?: string
    thumbnail_url?: string
  }
  search_text?: string
}

export interface AIMessagePayload {
  content: string | null
  attachments?: Array<{ type: 'image'; url: string; mime_type?: string }>
  page_context?: AIPageContext
  task_submission?: {
    task_id: string
    task_type: 'create_project' | 'publish_package' | 'publish_work' | 'project_application' | 'create_booking'
    action: 'publish' | 'save_draft' | 'cancel'
    revision: number
    form_data: Record<string, unknown>
    media_refs?: string[]
    idempotency_key: string
  }
  shoot_context_selection?: {
    source_message_id: number
    latitude: number
    longitude: number
  }
  generation_request?: AIImageGenerationRequest
}

export type AIImageGenerationMode = 'text_to_image' | 'image_to_image'
export type AIImageGenerationAspectRatio = '1:1' | '3:4' | '4:3' | '9:16' | '16:9'

export interface AIImageGenerationRequest {
  mode: AIImageGenerationMode
  aspect_ratio: AIImageGenerationAspectRatio
  count: 1 | 2
  quality: 'standard' | 'high'
  strength?: number
  idempotency_key: string
}

export interface AIImageGenerationAsset {
  id: number
  storage_url: string
  thumbnail_url?: string | null
  mime_type: string
  width?: number | null
  height?: number | null
  size_bytes?: number | null
  position: number
}

export interface AIImageGenerationJob {
  job_id: number
  task_id: string
  mode: AIImageGenerationMode
  status: 'queued' | 'generating' | 'retry_wait' | 'partial' | 'completed' | 'failed' | 'cancelled' | string
  stage: string
  progress: { completed: number; total: number }
  source_images: AIImageGenerationAsset[]
  result_images: AIImageGenerationAsset[]
  parameters: Record<string, unknown>
  provider?: string | null
  model?: string | null
  can_retry: boolean
  can_cancel: boolean
  error?: { code?: string; message?: string } | null
  created_at?: string
  updated_at?: string
}

export interface AIShootContextPlace {
  name: string
  address?: string
  latitude: number
  longitude: number
  coordinate_system?: string
  provider?: string
}

export interface AIShootContextWeatherHour {
  time: string
  temperature_c?: number | null
  precipitation_probability?: number | null
  cloud_cover?: number | null
  wind_kph?: number | null
  visibility_km?: number | null
}

export interface AIShootContext {
  schema_version: 'shoot_context_v1' | string
  status: 'success' | 'partial' | 'ambiguous' | 'failed' | string
  place?: AIShootContextPlace | null
  weather?: {
    timezone?: string
    forecast_date?: string
    hourly?: AIShootContextWeatherHour[]
    provider?: string
    updated_at?: string
  } | null
  sunlight?: {
    sunrise?: string | null
    sunset?: string | null
    golden_hour_start?: string | null
    golden_hour_end?: string | null
    blue_hour_end?: string | null
  } | null
  recommendations?: Array<{
    code?: string
    severity?: 'info' | 'warning' | string
    title: string
    detail: string
  }>
  place_candidates?: AIShootContextPlace[]
  error_code?: string | null
}

// ── Existing types ──

export interface AIConversation {
  id: string | number
  title?: string
  archived_at?: string | null
  created_at: string
  updated_at: string
}

// ── Reference item types for AI recommendations ──

export interface RefPhotographer {
  user_id?: number | string
  id?: number | string
  user_avatar_url?: string
  avatar_url?: string
  user_display_name?: string
  name?: string
}

export interface RefPortfolioItem {
  id?: number | string
  title?: string
  thumbnail_url?: string
  url?: string
}

export interface RefPackage {
  id?: number | string
  package_name?: string
  name?: string
  samples?: string[]
}

export interface RefProject {
  id?: number | string
  title?: string
  city?: string
  match_reason?: string
  reference_images?: string[]
  budget_label?: string
  date_label?: string
  status?: string
}

export interface AIMessage {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  attachments?: { type: string; url: string; mime_type?: string }[]
  page_context?: AIPageContext
  metadata?: {
    references?: {
      photographers?: RefPhotographer[]
      portfolio_items?: RefPortfolioItem[]
      packages?: RefPackage[]
      projects?: RefProject[]
    }
    shoot_context?: AIShootContext
    web_reference_images?: {
      schema_version?: string
      items?: Array<{
        image_url: string
        source_url: string
        title?: string
        alt?: string
        domain?: string
      }>
    }
    [key: string]: any
  }
  created_at: string
}

export interface AIChatResponse {
  user_message: AIMessage
  assistant_message: AIMessage
  active_task: AgentTask | null
}

export interface AIUploadResponse {
  url: string
  mime_type: string
  thumb_url?: string
  width: number
  height: number
  size_bytes: number
  sha256: string
  original_width: number
  original_height: number
  original_size_bytes: number
  normalized: boolean
}

export type PublishPolishContentType = 'project' | 'package' | 'work'

export interface PublishPolishResponse {
  fields: Record<string, unknown>
  polished_field_count: number
}

// ── Client Action types for agent-driven navigation ──

export interface WorkPublishDraft {
  title: string
  description: string
  tags: string[]
}

export interface ClientAction {
  type: 'open_work_publisher' | 'open_project_application'
  label: string
  draft?: WorkPublishDraft
  project_id?: number | string
}

export async function createAIConversation(data?: Record<string, unknown>): Promise<AIConversation> {
  const { data: res } = await api.post<AIConversation>('/ai/conversations', data || {})
  return res
}

export async function getAIConversations(params = {}): Promise<AIConversation[]> {
  const { data } = await api.get<AIConversation[]>('/ai/conversations', { params })
  return data
}

export async function searchAIConversations(params: Record<string, unknown> = {}): Promise<AIConversation[]> {
  const { data } = await api.get<AIConversation[]>('/ai/conversations/search', { params })
  return data
}

export async function forkAIConversation(conversationId: string | number, payload: { task_id?: string; turn_id?: number } = {}): Promise<AIConversation> {
  const { data } = await api.post<AIConversation>(`/ai/conversations/${conversationId}/fork`, payload)
  return data
}

export async function updateAIConversation(
  conversationId: string | number,
  data: { title?: string | null; archived?: boolean },
): Promise<AIConversation> {
  const { data: conversation } = await api.patch<AIConversation>(`/ai/conversations/${conversationId}`, data)
  return conversation
}

export async function getAIMessages(conversationId: string | number, params = {}): Promise<AIMessage[]> {
  const { data } = await api.get<AIMessage[]>(`/ai/conversations/${conversationId}/messages`, { params })
  return data
}

export async function sendAIMessage(conversationId: string | number, data: AIMessagePayload & Record<string, unknown>): Promise<AIChatResponse> {
  const { data: res } = await api.post<AIChatResponse>(
    `/ai/conversations/${conversationId}/messages`,
    data,
    { timeout: 70000 } as any,
  )
  return res
}

export async function uploadAIImage(file: File): Promise<AIUploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<AIUploadResponse>('/ai/uploads', form)
  return data
}

export async function getImageGeneration(jobId: number): Promise<AIImageGenerationJob> {
  const { data } = await api.get<AIImageGenerationJob>(`/ai/image-generations/${jobId}`)
  return data
}

export async function retryImageGeneration(jobId: number): Promise<AIImageGenerationJob> {
  const { data } = await api.post<AIImageGenerationJob>(`/ai/image-generations/${jobId}/retry`)
  return data
}

export async function regenerateImageGeneration(jobId: number): Promise<AIImageGenerationJob> {
  const { data } = await api.post<AIImageGenerationJob>(`/ai/image-generations/${jobId}/regenerate`)
  return data
}

export async function cancelImageGeneration(jobId: number): Promise<AIImageGenerationJob> {
  const { data } = await api.post<AIImageGenerationJob>(`/ai/image-generations/${jobId}/cancel`)
  return data
}

export async function polishPublishFields(
  contentType: PublishPolishContentType,
  fields: Record<string, unknown>,
): Promise<PublishPolishResponse> {
  const { data } = await api.post<PublishPolishResponse>('/ai/publish/polish', {
    content_type: contentType,
    fields,
  }, { timeout: 70000 } as any)
  return data
}
