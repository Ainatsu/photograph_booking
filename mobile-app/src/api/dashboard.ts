import api from './client'

export interface PhotographerDashboardResponse {
  period: { range_key: string; label: string }
  summary: { period_orders: number; confirmed_shoots: number; completion_rate: number | null; avg_rating: number | null }
  todo: { pending_orders: number; reschedule_requests: number; orders_to_deliver: number; orders_waiting_review: number }
  schedule: { today_orders: number; next_order: { id: number; appointment_time: string } | null; upcoming_orders: Array<{ id: number; appointment_time: string }> }
  top_works: Array<{ id: string; title: string; thumbnail_url: string; like_count: number; favorite_count: number }>
  top_packages: Array<{ id: string; name: string; price: number | null; sample_url: string | null; favorite_count: number }>
  interactions: { new_followers: number; message_conversations: number; work_likes: number }
  content: { portfolio_count: number; package_count: number }
  revenue: { available: boolean }
  funnel: { nodes: Array<{ key: string; label: string; count: number; conversion_rate: number | null }> }
}

export async function getPhotographerDashboard(range = 'month'): Promise<PhotographerDashboardResponse> {
  const { data } = await api.get<PhotographerDashboardResponse>('/orders/dashboard', { params: { range } })
  return data
}

export interface PhotographerPublicDashboardResponse {
  trust: {
    completed_orders: number
    avg_rating: number | null
    rating_count: number
    rating_visible: boolean
    completion_rate: number | null
    completion_rate_visible: boolean
    completion_sample_count: number
    recent_order_activity: boolean
  }
  content: {
    portfolio_count: number
    package_count: number
    packages_with_samples: number
    recent_upload_count: number
  }
  top_works: Array<{
    id: string
    title: string
    thumbnail_url: string
    like_count: number
    favorite_count: number
    total_interactions: number
  }>
  top_packages: Array<{
    id: string
    name: string
    price: number | null
    sample_url: string | null
    favorite_count: number
  }>
}

export async function getPublicPhotographerDashboard(userId: number): Promise<PhotographerPublicDashboardResponse> {
  const { data } = await api.get<PhotographerPublicDashboardResponse>(`/orders/dashboard/public/${userId}`)
  return data
}
