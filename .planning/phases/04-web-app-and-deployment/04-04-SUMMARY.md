---
phase: 04-web-app-and-deployment
plan: 04
subsystem: infra
tags: [nextjs, vercel, deployment, predictions]

# Dependency graph
requires:
  - phase: 04-02
    provides: Calendar components (CalendarInteractive, MonthGrid, DetailPanel), predictions.json in public/data/
  - phase: 04-03
    provides: Methodology page at /methodology, eval_report.json
provides:
  - Production Next.js build verified locally (Task 1 complete)
  - Vercel deployment pending human verification (Task 2 at checkpoint)
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Next.js 16 Turbopack build: static routes for / and /methodology prerendered"
    - "predictions.json served from public/data/ as CDN asset — NOT in serverless bundle"
    - "Top-3-days-per-month export strategy for year-round calendar coverage"

key-files:
  created: []
  modified:
    - web/public/data/predictions.json
    - web/components/DetailPanel.tsx
    - pipeline/model/export_predictions.py

key-decisions:
  - "predictions.json export strategy: top-3-days-per-month by max risk score (not global 90th percentile threshold) — produces 30 high-risk dates across all 10 months at 72KB"
  - "DetailPanel aspect labels: human-readable format (e.g., 'Sun Trine Jupiter') with per-type explanatory text"
  - ".next/dev/ (109MB Turbopack dev cache) is local only — actual Vercel deployment artifacts are ~7MB (build 792K + server 5.1M + static 980K)"

patterns-established:
  - "Vercel deployment: Root Directory = web in project settings; no vercel.json needed"

requirements-completed:
  - DEPLOY-02

# Metrics
duration: partial (paused at checkpoint)
completed: 2026-03-19
---

# Phase 04 Plan 04: Vercel Deployment Summary

**Next.js 16 production build verified locally — static routes for / and /methodology pass, predictions.json (72KB) confirmed as CDN asset not bundled into serverless function**

## Status: PAUSED AT CHECKPOINT

Task 1 complete. Paused at Task 2 (human verification of Vercel deployment).

## Performance

- **Duration:** ~10 min (Task 1 only)
- **Started:** 2026-03-19
- **Completed:** In progress (paused at checkpoint:human-verify)
- **Tasks:** 1 of 2 complete
- **Files modified:** 3

## Accomplishments

- Production build exits 0 with Turbopack — no TypeScript errors, no module resolution errors
- Static routes generated for `/` and `/methodology` (prerendered as static content)
- `predictions.json` confirmed NOT in serverless bundle (`find web/.next/server -name "predictions.json"` returns empty)
- Actual Vercel deployment artifacts ~7MB (well within 250MB limit)
- Updated `predictions.json` to top-3-days-per-month strategy: 30 high-risk dates across all 10 months, 72KB

## Task Commits

1. **Task 1: Run production build and verify output** - `2ba02d6` (feat)

## Files Created/Modified

- `web/public/data/predictions.json` — Updated: top-3-per-month export, 30 high-risk dates Mar-Dec 2026 (72KB)
- `web/components/DetailPanel.tsx` — Updated: human-readable aspect labels with per-type descriptions
- `pipeline/model/export_predictions.py` — Updated: top-3-days-per-month selection strategy

## Decisions Made

- `predictions.json` export updated to top-3-days-per-month (not global threshold) — ensures year-round calendar coverage with dates across all 10 months
- `.next/dev/` (109MB local Turbopack cache) is NOT part of Vercel deployment — actual artifacts ~7MB total
- DetailPanel aspect formatting: machine names like `sun_moon_conjunction` rendered as "Sun Moon Conjunction" with explanatory descriptions for each aspect type

## Deviations from Plan

None - plan executed exactly as written for Task 1. Task 2 is a checkpoint requiring human action.

## User Setup Required (Task 2 — Pending)

**Vercel deployment requires manual configuration:**

1. Go to [vercel.com](https://vercel.com) and import the GitHub repository
2. In "Configure Project", set **Root Directory** to `web`
3. Click Deploy — Vercel auto-detects Next.js and fills Build Command (`next build`) and Output Dir (`.next`)
4. After deploy, verify the URL serves the calendar, methodology page, and disclaimer

**Alternative (CLI):**
```
cd web && npx vercel --yes
```
When prompted for Root Directory, enter `web`.

## Next Phase Readiness

- Task 1 DONE: Local production build verified, all acceptance criteria pass
- Task 2 PENDING: Awaiting human Vercel deployment and URL verification
- After Task 2: Phase 04 complete, all DEPLOY requirements fulfilled

---
*Phase: 04-web-app-and-deployment*
*Completed: 2026-03-19 (partial — Task 2 pending)*
