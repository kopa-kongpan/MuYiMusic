export interface DateRangeValue {
  startDate: string
  endDate: string
}

export type DateRangePreset =
  | 'this-week'
  | 'next-week'
  | 'this-month'
  | 'custom'

export function formatLocalDate(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function startOfWeek(value: Date): Date {
  const result = new Date(value.getFullYear(), value.getMonth(), value.getDate())
  const offset = result.getDay() === 0 ? -6 : 1 - result.getDay()
  result.setDate(result.getDate() + offset)
  return result
}

function addDays(value: Date, days: number): Date {
  const result = new Date(value)
  result.setDate(result.getDate() + days)
  return result
}

export function shiftDate(date: string, days: number): string {
  return formatLocalDate(addDays(new Date(`${date}T00:00:00`), days))
}

export function presetDateRange(
  preset: Exclude<DateRangePreset, 'custom'>,
  current = new Date(),
): DateRangeValue {
  if (preset === 'this-month') {
    return {
      startDate: formatLocalDate(
        new Date(current.getFullYear(), current.getMonth(), 1),
      ),
      endDate: formatLocalDate(
        new Date(current.getFullYear(), current.getMonth() + 1, 0),
      ),
    }
  }

  const thisWeekStart = startOfWeek(current)
  const startDate =
    preset === 'next-week' ? addDays(thisWeekStart, 7) : thisWeekStart
  return {
    startDate: formatLocalDate(startDate),
    endDate: formatLocalDate(addDays(startDate, 6)),
  }
}

export function dateRangeWindow(value: DateRangeValue): {
  startsFrom: string
  startsBefore: string
} {
  const startsFrom = new Date(`${value.startDate}T00:00:00`)
  const startsBefore = new Date(`${value.endDate}T00:00:00`)
  startsBefore.setDate(startsBefore.getDate() + 1)
  return {
    startsFrom: startsFrom.toISOString(),
    startsBefore: startsBefore.toISOString(),
  }
}
