import { promises as fs } from 'fs'
import path from 'path'

export interface Prediction {
  date: string                    // ISO "2026-03-08"
  country: string
  lat: number
  lon: number
  risk_score: number              // 0-1 float
  top_planetary_aspects: string[] // up to 3 strings
}

export interface EvalReport {
  model_used: string
  f1_score: number
  mcc: number
  threshold: number
  eval_split_date: string
  confusion_matrix: { tp: number; fp: number; fn: number; tn: number }
  both_models: Array<{ model: string; f1: number; mcc: number }>
}

export async function loadPredictions(): Promise<Prediction[]> {
  const filePath = path.join(process.cwd(), 'public/data/predictions.json')
  const raw = await fs.readFile(filePath, 'utf8')
  return JSON.parse(raw) as Prediction[]
}

export async function loadEvalReport(): Promise<EvalReport> {
  const filePath = path.join(process.cwd(), 'public/data/eval_report.json')
  const raw = await fs.readFile(filePath, 'utf8')
  return JSON.parse(raw) as EvalReport
}

export function groupPredictionsByDate(predictions: Prediction[]): Record<string, Prediction[]> {
  const byDate: Record<string, Prediction[]> = {}
  for (const p of predictions) {
    if (!byDate[p.date]) byDate[p.date] = []
    byDate[p.date].push(p)
  }
  return byDate
}
