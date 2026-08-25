export interface NotificationRecord {
  id: number
  order_id?: number | null
  project_id?: number | null
  notification_type: string
  title: string
  content: string
  action_url?: string | null
  is_read: boolean
  read_at?: string | null
  created_at: string
}

export interface NotificationListParams {
  unread_only?: boolean
  skip?: number
  limit?: number
}

export interface NotificationMutationResult {
  updated: number
}
