import { Input, Segmented } from 'antd'
import { useState } from 'react'

import {
  type DateRangePreset,
  type DateRangeValue,
  presetDateRange,
  shiftDate,
} from './dateRange'

const presetOptions: Array<{ label: string; value: DateRangePreset }> = [
  { label: '本周', value: 'this-week' },
  { label: '下周', value: 'next-week' },
  { label: '本月', value: 'this-month' },
  { label: '自定义', value: 'custom' },
]

interface DateRangeFilterProps {
  value: DateRangeValue
  labelPrefix: string
  onChange: (value: DateRangeValue) => void
}

export function DateRangeFilter({
  value,
  labelPrefix,
  onChange,
}: DateRangeFilterProps) {
  const [activePreset, setActivePreset] =
    useState<DateRangePreset>('this-week')

  function selectPreset(preset: DateRangePreset) {
    setActivePreset(preset)
    if (preset !== 'custom') {
      onChange(presetDateRange(preset))
    }
  }

  function changeStartDate(startDate: string) {
    if (!startDate) return
    setActivePreset('custom')
    const latestEndDate = shiftDate(startDate, 30)
    onChange({
      startDate,
      endDate:
        startDate > value.endDate
          ? startDate
          : value.endDate > latestEndDate
            ? latestEndDate
            : value.endDate,
    })
  }

  function changeEndDate(endDate: string) {
    if (!endDate) return
    setActivePreset('custom')
    const earliestStartDate = shiftDate(endDate, -30)
    onChange({
      startDate:
        endDate < value.startDate
          ? endDate
          : value.startDate < earliestStartDate
            ? earliestStartDate
            : value.startDate,
      endDate,
    })
  }

  return (
    <div className="date-range-filter">
      <Segmented
        size="small"
        value={activePreset}
        options={presetOptions}
        onChange={(preset) => selectPreset(preset as DateRangePreset)}
      />
      <div className="date-range-inputs">
        <Input
          type="date"
          value={value.startDate}
          min={shiftDate(value.endDate, -30)}
          aria-label={`${labelPrefix}开始日期`}
          onChange={(event) => changeStartDate(event.target.value)}
        />
        <span>至</span>
        <Input
          type="date"
          value={value.endDate}
          max={shiftDate(value.startDate, 30)}
          aria-label={`${labelPrefix}结束日期`}
          onChange={(event) => changeEndDate(event.target.value)}
        />
      </div>
    </div>
  )
}
