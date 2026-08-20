import { describe, expect, it } from 'vitest'

import { dateRangeWindow, presetDateRange, shiftDate } from './dateRange'

describe('presetDateRange', () => {
  const current = new Date(2026, 7, 20, 12)

  it('uses Monday through Sunday for this week', () => {
    expect(presetDateRange('this-week', current)).toEqual({
      startDate: '2026-08-17',
      endDate: '2026-08-23',
    })
  })

  it('returns the following Monday through Sunday', () => {
    expect(presetDateRange('next-week', current)).toEqual({
      startDate: '2026-08-24',
      endDate: '2026-08-30',
    })
  })

  it('returns the complete current month', () => {
    expect(presetDateRange('this-month', current)).toEqual({
      startDate: '2026-08-01',
      endDate: '2026-08-31',
    })
  })
})

describe('dateRangeWindow', () => {
  it('uses the day after the selected end date as the exclusive upper bound', () => {
    const result = dateRangeWindow({
      startDate: '2026-08-17',
      endDate: '2026-08-23',
    })

    expect(new Date(result.startsFrom).getDate()).toBe(17)
    expect(new Date(result.startsBefore).getDate()).toBe(24)
  })
})

describe('shiftDate', () => {
  it('moves across month boundaries in local calendar days', () => {
    expect(shiftDate('2026-08-31', 1)).toBe('2026-09-01')
    expect(shiftDate('2026-09-01', -30)).toBe('2026-08-02')
  })
})
