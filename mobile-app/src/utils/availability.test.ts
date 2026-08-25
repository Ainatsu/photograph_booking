import { describe, expect, it } from 'vitest'
import {
  buildAvailabilityCalendar,
  buildAvailabilityExceptions,
  dateRangeKeys,
  hydrateAvailabilityDays,
  parseDateKey,
  setAvailabilityDay,
  toDateKey,
} from './availability'

const today = new Date(2026, 6, 23)

describe('availability helpers', () => {
  it('parses strict local date keys without rolling invalid dates forward', () => {
    expect(toDateKey(new Date(2026, 6, 3))).toBe('2026-07-03')
    expect(parseDateKey('2026-02-29')).toBeNull()
    expect(parseDateKey('2026/07/23')).toBeNull()
  })

  it('hydrates future busy days and location-only exceptions', () => {
    const days = hydrateAvailabilityDays([
      { date: '2026-07-22', status: 'busy' },
      { date: '2026-07-24', status: 'busy', location: '香港中环' },
      { date: '2026-07-25', status: 'free', location: '九龙' },
      { date: '2026-07-26', status: 'free' },
    ], today)

    expect(days).toEqual({
      '2026-07-24': { status: 'busy', location: '香港中环' },
      '2026-07-25': { status: 'free', location: '九龙' },
    })
  })

  it('removes default free days and builds sorted server exceptions', () => {
    let days = setAvailabilityDay({}, '2026-07-25', 'busy', '', today)
    days = setAvailabilityDay(days, '2026-07-24', 'free', '澳门', today)
    days = setAvailabilityDay(days, '2026-07-25', 'free', '', today)

    expect(buildAvailabilityExceptions(days, today)).toEqual([
      { date: '2026-07-24', status: 'free', location: '澳门' },
    ])
  })

  it('creates inclusive ranges regardless of selection direction', () => {
    expect(dateRangeKeys('2026-07-26', '2026-07-24', today)).toEqual([
      '2026-07-24',
      '2026-07-25',
      '2026-07-26',
    ])
  })

  it('builds a Monday-first calendar with disabled past dates and selected state', () => {
    const cells = buildAvailabilityCalendar(
      new Date(2026, 6, 1),
      { '2026-07-24': { status: 'busy' } },
      { today, selectedKeys: ['2026-07-24'] },
    )
    const firstDate = cells.find((cell) => !cell.isBlank)
    const past = cells.find((cell) => cell.key === '2026-07-22')
    const selected = cells.find((cell) => cell.key === '2026-07-24')

    expect(cells.slice(0, 2).every((cell) => cell.isBlank)).toBe(true)
    expect(firstDate?.key).toBe('2026-07-01')
    expect(past?.disabled).toBe(true)
    expect(selected).toMatchObject({ status: 'busy', isSelected: true, disabled: false })
  })
})
