'use client'

import type { Prediction } from '@/lib/predictions'

interface DetailPanelProps {
  predictions: Prediction[]
  date: string
  onClose: () => void
}

function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  const d = new Date(year, month - 1, day)
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
}

export function DetailPanel({ predictions, date, onClose }: DetailPanelProps) {
  const sorted = [...predictions].sort((a, b) => b.risk_score - a.risk_score)
  const maxRiskScore = sorted[0]?.risk_score ?? 0
  const topAspects = sorted[0]?.top_planetary_aspects ?? []

  return (
    <>
      <div
        className="fixed inset-0 bg-black/20 z-40"
        onClick={onClose}
      />
      <div className="fixed right-0 top-0 h-full w-full md:w-80 lg:w-96 bg-white shadow-xl transform transition-transform duration-300 ease-in-out translate-x-0 overflow-y-auto z-50 p-6">
        <h2 className="text-lg font-semibold">{formatDate(date)}</h2>

        <div className="mt-4">
          <span className="text-3xl font-semibold">{maxRiskScore.toFixed(2)}</span>
          <div className="h-2 bg-orange-200 rounded mt-1">
            <div
              className="h-2 bg-orange-500 rounded"
              style={{ width: `${maxRiskScore * 100}%` }}
            />
          </div>
        </div>

        <div className="mt-4">
          {sorted.map((p, idx) => (
            <div key={idx} className="mt-3 text-sm">
              <span className="font-medium">{p.country}</span>
              <span className="text-gray-500"> — lat {p.lat}, lon {p.lon}</span>
            </div>
          ))}
        </div>

        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mt-4">
          Top Planetary Aspects
        </h3>
        <ul className="mt-1 space-y-1 text-sm">
          {topAspects.map((aspect, idx) => (
            <li key={idx}>{aspect.replace(/_/g, ' ')}</li>
          ))}
        </ul>
      </div>
    </>
  )
}
