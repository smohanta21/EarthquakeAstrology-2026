'use client'

import { useState } from 'react'
import type { Prediction } from '@/lib/predictions'
import { MonthGrid } from './MonthGrid'
import { DetailPanel } from './DetailPanel'

interface DateCell {
  date: string
  dayNum: number
  isHighRisk: boolean
  isEmpty: boolean
}

interface MonthData {
  year: number
  month: number  // 0-indexed (2=March)
  label: string
}

interface CalendarInteractiveProps {
  predictionsByDate: Record<string, Prediction[]>
  months: MonthData[]
}

function getWeekDates(dateStr: string): string[] {
  const [year, month, day] = dateStr.split('-').map(Number)
  const date = new Date(year, month - 1, day)
  const dayOfWeek = date.getDay() // 0=Sunday
  const sunday = new Date(date)
  sunday.setDate(date.getDate() - dayOfWeek)

  const weekDates: string[] = []
  for (let i = 0; i < 7; i++) {
    const d = new Date(sunday)
    d.setDate(sunday.getDate() + i)
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    weekDates.push(`${y}-${m}-${day}`)
  }
  return weekDates
}

function buildCells(
  year: number,
  month: number, // 0-indexed
  predictionsByDate: Record<string, Prediction[]>
): DateCell[] {
  const firstDay = new Date(year, month, 1)
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const startWeekday = firstDay.getDay() // 0=Sunday

  const cells: DateCell[] = []

  // Leading empty cells
  for (let i = 0; i < startWeekday; i++) {
    cells.push({ date: '', dayNum: 0, isHighRisk: false, isEmpty: true })
  }

  // Day cells
  for (let d = 1; d <= daysInMonth; d++) {
    const m = String(month + 1).padStart(2, '0')
    const day = String(d).padStart(2, '0')
    const dateStr = `${year}-${m}-${day}`
    cells.push({
      date: dateStr,
      dayNum: d,
      isHighRisk: dateStr in predictionsByDate,
      isEmpty: false,
    })
  }

  return cells
}

export function CalendarInteractive({ predictionsByDate, months }: CalendarInteractiveProps) {
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [highlightedWeek, setHighlightedWeek] = useState<string[] | null>(null)

  function handleDateClick(date: string, isHighRisk: boolean) {
    if (isHighRisk) {
      setSelectedDate(date)
      setHighlightedWeek(null)
    } else {
      setSelectedDate(null)
      const weekDates = getWeekDates(date)
      const highRiskInWeek = weekDates.filter((d) => d in predictionsByDate)
      setHighlightedWeek(highRiskInWeek.length > 0 ? highRiskInWeek : null)
    }
  }

  return (
    <div className="px-4 py-8 md:px-8">
      <h2 className="text-lg font-semibold mb-4">2026 Earthquake Risk Calendar</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {months.map((month) => {
          const cells = buildCells(month.year, month.month, predictionsByDate)
          return (
            <MonthGrid
              key={month.label}
              label={month.label}
              cells={cells}
              predictionsByDate={predictionsByDate}
              selectedDate={selectedDate}
              highlightedWeek={highlightedWeek}
              onDateClick={handleDateClick}
            />
          )
        })}
      </div>
      {selectedDate && predictionsByDate[selectedDate] && (
        <DetailPanel
          predictions={predictionsByDate[selectedDate]}
          date={selectedDate}
          onClose={() => setSelectedDate(null)}
        />
      )}
    </div>
  )
}
