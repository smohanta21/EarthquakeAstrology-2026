import { loadPredictions, groupPredictionsByDate } from '@/lib/predictions'

export default async function CalendarPage() {
  const predictions = await loadPredictions()
  const predictionsByDate = groupPredictionsByDate(predictions)
  const uniqueDates = Object.keys(predictionsByDate).sort()

  return (
    <div className="px-4 py-8 md:px-8">
      <h2 className="text-lg font-semibold mb-4">
        2026 Earthquake Risk Calendar
      </h2>
      <p className="text-sm text-gray-600">
        {predictions.length} predictions across {uniqueDates.length} date(s).
        Calendar grid coming in Plan 02.
      </p>
    </div>
  )
}
