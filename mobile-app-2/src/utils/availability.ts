import type { AvailabilityException, AvailabilityStatus } from '@/types/discovery'

export interface AvailabilityDayState {
  status: AvailabilityStatus
  location?: string
}

export type AvailabilityDayMap = Record<string, AvailabilityDayState>

export interface AvailabilityCalendarCell {
  key: string
  isBlank: boolean
  day?: number
  date?: Date
  status?: AvailabilityStatus
  location?: string
  disabled?: boolean
  isToday?: boolean
  isSelected?: boolean
  isRangeStart?: boolean
  isRangeEnd?: boolean
  isInRange?: boolean
}

export const MAX_AVAILABILITY_DAYS = 365

export function startOfLocalDay(value = new Date()): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

export function addDays(value: Date, days: number): Date {
  const next = new Date(value)
  next.setDate(next.getDate() + days)
  return next
}

export function addMonths(value: Date, months: number): Date {
  return new Date(value.getFullYear(), value.getMonth() + months, 1)
}

export function toDateKey(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function parseDateKey(value?: string | null): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ''))
  if (!match) return null
  const year = Number(match[1])
  const month = Number(match[2]) - 1
  const day = Number(match[3])
  const date = new Date(year, month, day)
  if (date.getFullYear() !== year || date.getMonth() !== month || date.getDate() !== day) return null
  return date
}

export function normalizeAvailabilityStatus(value: unknown): AvailabilityStatus {
  return value === 'busy' || value === 'closed' ? 'busy' : 'free'
}

export function isAvailabilityDateAllowed(
  value: Date,
  today = startOfLocalDay(),
  maxDays = MAX_AVAILABILITY_DAYS,
): boolean {
  const normalizedToday = startOfLocalDay(today)
  return value >= normalizedToday && value <= addDays(normalizedToday, maxDays)
}

export function getAvailabilityDay(days: AvailabilityDayMap, dateKey: string): AvailabilityDayState {
  return days[dateKey] || { status: 'free', location: '' }
}

export function setAvailabilityDay(
  days: AvailabilityDayMap,
  dateKey: string,
  status: AvailabilityStatus,
  location = '',
  today = startOfLocalDay(),
): AvailabilityDayMap {
  const date = parseDateKey(dateKey)
  if (!date || !isAvailabilityDateAllowed(date, today)) return days

  const next = { ...days }
  const normalizedStatus = normalizeAvailabilityStatus(status)
  const normalizedLocation = String(location || '').trim().slice(0, 60)
  if (normalizedStatus === 'free' && !normalizedLocation) {
    delete next[dateKey]
  } else {
    next[dateKey] = {
      status: normalizedStatus,
      ...(normalizedLocation ? { location: normalizedLocation } : {}),
    }
  }
  return next
}

export function hydrateAvailabilityDays(
  entries: AvailabilityException[] | null | undefined,
  today = startOfLocalDay(),
): AvailabilityDayMap {
  let days: AvailabilityDayMap = {}
  for (const entry of entries || []) {
    const dateKey = String(entry?.date || '').split('T')[0]
    const date = parseDateKey(dateKey)
    if (!date || !isAvailabilityDateAllowed(date, today)) continue
    days = setAvailabilityDay(
      days,
      dateKey,
      normalizeAvailabilityStatus(entry.status),
      entry.location || '',
      today,
    )
  }
  return days
}

export function buildAvailabilityExceptions(
  days: AvailabilityDayMap,
  today = startOfLocalDay(),
): AvailabilityException[] {
  return Object.entries(days)
    .map(([date, entry]) => ({
      date,
      status: normalizeAvailabilityStatus(entry.status),
      location: String(entry.location || '').trim(),
    }))
    .filter((entry) => {
      const date = parseDateKey(entry.date)
      return Boolean(date && isAvailabilityDateAllowed(date, today) && (entry.status === 'busy' || entry.location))
    })
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((entry) => ({
      date: entry.date,
      status: entry.status,
      ...(entry.location ? { location: entry.location } : {}),
    }))
}

export function dateRangeKeys(
  startKey: string,
  endKey: string,
  today = startOfLocalDay(),
): string[] {
  const firstKey = startKey.localeCompare(endKey) <= 0 ? startKey : endKey
  const lastKey = firstKey === startKey ? endKey : startKey
  const start = parseDateKey(firstKey)
  const end = parseDateKey(lastKey)
  if (!start || !end) return []

  const keys: string[] = []
  const cursor = new Date(start)
  while (cursor <= end) {
    if (isAvailabilityDateAllowed(cursor, today)) keys.push(toDateKey(cursor))
    cursor.setDate(cursor.getDate() + 1)
  }
  return keys
}

export function monthDateKeys(
  monthStart: Date,
  filter: (date: Date) => boolean = () => true,
  today = startOfLocalDay(),
): string[] {
  const daysInMonth = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0).getDate()
  const keys: string[] = []
  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = new Date(monthStart.getFullYear(), monthStart.getMonth(), day)
    if (isAvailabilityDateAllowed(date, today) && filter(date)) keys.push(toDateKey(date))
  }
  return keys
}

export function buildAvailabilityCalendar(
  monthStart: Date,
  days: AvailabilityDayMap,
  options: {
    today?: Date
    selectedKeys?: string[]
    rangeStart?: string
    rangeEnd?: string
  } = {},
): AvailabilityCalendarCell[] {
  const today = startOfLocalDay(options.today)
  const selected = new Set(options.selectedKeys || [])
  const rangeStart = options.rangeStart || ''
  const rangeEnd = options.rangeEnd || ''
  const normalizedRangeStart = rangeStart && rangeEnd && rangeStart.localeCompare(rangeEnd) <= 0 ? rangeStart : rangeEnd
  const normalizedRangeEnd = normalizedRangeStart === rangeStart ? rangeEnd : rangeStart
  const firstDayOffset = (monthStart.getDay() + 6) % 7
  const daysInMonth = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0).getDate()
  const cells: AvailabilityCalendarCell[] = Array.from({ length: firstDayOffset }, (_, index) => ({
    key: `blank-${index}`,
    isBlank: true,
  }))

  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = new Date(monthStart.getFullYear(), monthStart.getMonth(), day)
    const key = toDateKey(date)
    const entry = getAvailabilityDay(days, key)
    cells.push({
      key,
      day,
      date,
      status: normalizeAvailabilityStatus(entry.status),
      location: entry.location || '',
      isBlank: false,
      disabled: !isAvailabilityDateAllowed(date, today),
      isToday: key === toDateKey(today),
      isSelected: selected.has(key),
      isRangeStart: key === rangeStart,
      isRangeEnd: key === rangeEnd,
      isInRange: Boolean(normalizedRangeStart && normalizedRangeEnd && key >= normalizedRangeStart && key <= normalizedRangeEnd),
    })
  }
  return cells
}
