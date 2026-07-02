import type { Prediction } from '@/lib/predictions'

interface DateCell {
  date: string
  dayNum: number
  isHighRisk: boolean
  isEmpty: boolean
}

interface MonthGridProps {
  label: string
  cells: DateCell[]
  predictionsByDate: Record<string, Prediction[]>
  selectedDate: string | null
  highlightedWeek: string[] | null
  onDateClick: (date: string, isHighRisk: boolean) => void
}

const DAY_HEADERS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

export function MonthGrid({
  label,
  cells,
  selectedDate,
  highlightedWeek,
  onDateClick,
}: MonthGridProps) {
  return (
    <div className="mb-8">
      <h2 className="text-sm font-semibold text-gray-600 mb-2">{label}</h2>
      <div className="grid grid-cols-7 gap-1">
        {DAY_HEADERS.map((day) => (
          <div key={day} className="text-xs text-center text-gray-400 py-1">
            {day}
          </div>
        ))}
        {cells.map((cell, idx) => {
          if (cell.isEmpty) {
            return <div key={`empty-${idx}`} className="aspect-square" />
          }

          const isSelected = selectedDate === cell.date
          const isWeekHighlighted =
            cell.isHighRisk &&
            highlightedWeek !== null &&
            highlightedWeek.includes(cell.date)

          let cellClasses = 'aspect-square rounded text-sm flex items-start justify-start p-1 '

          if (cell.isHighRisk) {
            cellClasses += 'bg-orange-400 cursor-pointer hover:bg-orange-500'
            if (isSelected) {
              cellClasses += ' ring-2 ring-orange-600'
            } else if (isWeekHighlighted) {
              cellClasses += ' ring-2 ring-orange-400'
            }
          } else {
            cellClasses += 'bg-gray-50 cursor-pointer hover:bg-gray-100'
          }

          return (
            <div
              key={cell.date}
              className={cellClasses}
              onClick={() => onDateClick(cell.date, cell.isHighRisk)}
            >
              <span
                className={
                  cell.isHighRisk
                    ? 'text-white text-xs font-medium'
                    : 'text-gray-700 text-xs'
                }
              >
                {cell.dayNum}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
