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

const ASPECT_DESCRIPTIONS: Record<string, string> = {
  conjunction: 'Two planets aligned — their energies merge and amplify each other.',
  opposition: 'Two planets directly across from each other — creates tension and stress between opposing forces.',
  square: 'Two planets at a 90° angle — friction and dynamic tension that can trigger seismic activity.',
  trine: 'Two planets 120° apart — energy flows easily, a smoother but still notable alignment.',
  sextile: 'Two planets 60° apart — mild cooperative energy with moderate influence.',
}

function formatAspect(aspect: string): { label: string; description: string } {
  const types = ['conjunction', 'opposition', 'trine', 'square', 'sextile']
  for (const type of types) {
    if (aspect.endsWith('_' + type)) {
      const bodyPart = aspect.slice(0, -(type.length + 1))
      const bodies = bodyPart.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1))
      const label = bodies.length === 2
        ? `${bodies[0]} ${type.charAt(0).toUpperCase() + type.slice(1)} ${bodies[1]}`
        : `${bodies.join(' ')} ${type.charAt(0).toUpperCase() + type.slice(1)}`
      return { label, description: ASPECT_DESCRIPTIONS[type] ?? '' }
    }
  }
  return { label: aspect.replace(/_/g, ' '), description: '' }
}

export function DetailPanel({ predictions, date, onClose }: DetailPanelProps) {
  const sorted = [...predictions].sort((a, b) => b.risk_score - a.risk_score)
  const maxRiskScore = sorted[0]?.risk_score ?? 0
  const topAspects = sorted[0]?.top_planetary_aspects ?? []
  const topLocations = sorted.slice(0, 3)

  return (
    <>
      <div
        className="fixed inset-0 bg-black/20 z-40"
        onClick={onClose}
      />
      <div className="fixed right-0 top-0 h-full w-full md:w-80 lg:w-96 bg-white shadow-xl transform transition-transform duration-300 ease-in-out translate-x-0 overflow-y-auto z-50 p-6">
        <h2 className="text-lg font-semibold">{formatDate(date)}</h2>

        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mt-4">
          Planetary Aspects
        </h3>
        <ul className="mt-2 space-y-3">
          {topAspects.map((aspect, idx) => {
            const { label, description } = formatAspect(aspect)
            return (
              <li key={idx}>
                <div className="text-base font-medium">{label}</div>
                {description && <div className="text-sm text-gray-500 mt-0.5">{description}</div>}
              </li>
            )
          })}
        </ul>

        <div className="mt-5">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Risk Score</span>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-2xl font-semibold">{maxRiskScore.toFixed(2)}</span>
            <div className="flex-1 h-2 bg-orange-200 rounded">
              <div
                className="h-2 bg-orange-500 rounded"
                style={{ width: `${maxRiskScore * 100}%` }}
              />
            </div>
          </div>
        </div>

        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mt-5">
          Top Locations
        </h3>
        <div className="mt-2">
          {topLocations.map((p, idx) => (
            <div key={idx} className="mt-2 text-sm">
              <span className="font-medium">{p.country}</span>
              <span className="text-gray-500"> — {p.lat}°, {p.lon}°</span>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
