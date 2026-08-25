import { AxiosError } from 'axios'
import api from './client'
import type {
  AvailabilityException,
  AvailableHoursEntry,
  PhotographerProfile,
} from '@/types/discovery'

export interface PhotographerSettingsPayload {
  equipment: string
  styles: string[]
  available_hours: AvailableHoursEntry[]
  availability_exceptions: AvailabilityException[]
  advance_notice: number
  max_daily_bookings: number
  max_booking_date: string
}

export async function getPhotographerSettings(
  userId: number,
): Promise<PhotographerProfile | null> {
  try {
    const { data } = await api.get<PhotographerProfile>(`/photographers/profile/${userId}`)
    return data
  } catch (error) {
    if (error instanceof AxiosError && error.response?.status === 404) return null
    throw error
  }
}

export async function savePhotographerSettings(
  payload: PhotographerSettingsPayload,
): Promise<PhotographerProfile> {
  const { data } = await api.post<PhotographerProfile>('/photographers/profile', payload)
  return data
}

/** 单独保存常驻地：资料与账号页只提交这一个字段，避免覆盖档期等其他设置。 */
export async function savePhotographerResidency(location: string): Promise<PhotographerProfile> {
  const { data } = await api.post<PhotographerProfile>('/photographers/profile', { location })
  return data
}
