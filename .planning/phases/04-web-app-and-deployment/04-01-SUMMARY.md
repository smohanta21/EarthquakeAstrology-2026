---
phase: 04-web-app-and-deployment
plan: 01
subsystem: ui
tags: [nextjs, react, tailwind, typescript, next-font, server-components]

# Dependency graph
requires:
  - phase: 03-model-training-and-prediction-export
    provides: predictions.json (901 entries) and eval_report.json (XGBClassifier metrics)
provides:
  - Next.js 16.1.7 app scaffolded in web/ with React 19, Tailwind CSS 4, TypeScript
  - Prediction and EvalReport type definitions exported from web/lib/predictions.ts
  - loadPredictions() and loadEvalReport() async Server Component data loaders using fs.readFile
  - groupPredictionsByDate() utility function
  - Root layout with non-dismissable amber disclaimer banner and nav bar
  - page.tsx Server Component reading predictions.json at build time (WEB-05 pattern established)
  - eval_report.json copied to web/public/data/ for methodology page (Plan 03)
affects: [04-02-calendar-grid, 04-03-methodology-page, 04-04-deployment]

# Tech tracking
tech-stack:
  added:
    - next 16.1.7
    - react 19.2.3
    - react-dom 19.2.3
    - tailwindcss 4 (CSS-first config via @import "tailwindcss")
    - typescript 5
    - "@types/node (for fs and path in Server Components)"
    - next/font/google (Inter font, zero layout shift)
  patterns:
    - "Server Component fs.readFile pattern: path.join(process.cwd(), 'public/data/...') — works locally and on Vercel"
    - "Data flows Server → Client: Server Component loads data at build time, passes as props to Client Components"
    - "Non-dismissable disclaimer: static HTML in root layout, no JS required, renders before nav and main"

key-files:
  created:
    - web/package.json
    - web/next.config.ts
    - web/tsconfig.json
    - web/app/globals.css
    - web/lib/predictions.ts
    - web/public/data/eval_report.json
  modified:
    - web/app/layout.tsx
    - web/app/page.tsx

key-decisions:
  - "npm cache had root-owned directories (permission error); workaround was npm_config_cache=/tmp/npm-cache for install"
  - "create-next-app failed with web/public/ conflict; predictions.json was backed up, scaffold run, then data restored"
  - "Tailwind CSS 4 globals.css uses @import tailwindcss CSS-first config — no tailwind.config.js needed"

patterns-established:
  - "Pattern WEB-05: async Server Component reads JSON via fs.readFile + path.join(process.cwd(), 'public/data/file.json')"
  - "Pattern Layout: disclaimer banner as first child of body, before nav, before main — non-dismissable, always visible"

requirements-completed: [WEB-04, WEB-05]

# Metrics
duration: 4min
completed: 2026-03-17
---

# Phase 4 Plan 01: Web App Scaffold Summary

**Next.js 16 app scaffolded in web/ with Prediction/EvalReport types, fs.readFile build-time data loading, Inter font, and non-dismissable disclaimer banner wrapping all pages**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-17T20:31:30Z
- **Completed:** 2026-03-17T20:35:30Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Next.js 16.1.7 + React 19 + Tailwind CSS 4 scaffolded in web/ with clean build
- Shared types (Prediction, EvalReport) and data loaders exported from web/lib/predictions.ts
- eval_report.json copied to web/public/data/ making both JSON files available at the same path prefix
- Root layout with non-dismissable amber disclaimer banner (WEB-04), Inter font, and nav with Methodology link
- page.tsx establishes WEB-05 pattern: Server Component reads predictions.json via fs.readFile at build time, zero client fetch

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold Next.js 16 app, copy eval_report.json, define types and data loaders** - `5556ff2` (feat)
2. **Task 2: Create root layout with disclaimer banner, nav bar, and placeholder page** - `da4a2ab` (feat)

## Files Created/Modified
- `web/package.json` - Next.js 16.1.7 project with React 19, Tailwind CSS 4, TypeScript
- `web/next.config.ts` - Minimal config, no webpack key (Turbopack default)
- `web/tsconfig.json` - TypeScript config with @/* path alias
- `web/app/globals.css` - Tailwind CSS 4 @import directive
- `web/lib/predictions.ts` - Prediction and EvalReport interfaces + loadPredictions, loadEvalReport, groupPredictionsByDate
- `web/public/data/eval_report.json` - Copy of data/models/eval_report.json for methodology page
- `web/app/layout.tsx` - Root layout: Inter font, disclaimer banner, nav bar with title and Methodology link
- `web/app/page.tsx` - Placeholder Server Component: reads predictions.json via fs.readFile, renders count

## Decisions Made
- npm cache had root-owned directories causing EACCES; workaround: `npm_config_cache=/tmp/npm-cache`
- create-next-app conflicts with existing web/public/ directory; predictions.json backed up to /tmp, scaffold ran, data restored
- Tailwind CSS 4 globals.css uses CSS-first `@import "tailwindcss"` — no tailwind.config.js required

## Deviations from Plan

None - plan executed exactly as written. The npm cache permission issue was a system-level setup problem, not a code deviation; worked around without modifying any planned files.

## Issues Encountered
- **npm cache permission error:** `/Users/adityasrivatsan/.npm/_cacache` contains root-owned directories from a previous npm run. Resolved by using `npm_config_cache=/tmp/npm-cache` for the install command. This does not affect the committed code or build output.
- **create-next-app public/ conflict:** The web/ directory already had public/data/predictions.json. Predictions.json was backed up to /tmp, scaffold ran successfully, then data file was restored.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Build foundation complete: Next.js 16 app compiles cleanly, all type definitions and data loaders exported
- Plan 02 can immediately build CalendarInteractive and MonthGrid components using Prediction type and groupPredictionsByDate()
- Plan 03 can use loadEvalReport() and EvalReport type for the methodology page
- Plan 04 (Vercel deployment) requires setting Root Directory = web in Vercel project settings (one-time dashboard action)
- Potential concern: predictions.json only has entries for 2026-03-08 (Phase 3 export issue noted in RESEARCH.md) — web app handles sparse data correctly per spec, does not block Phase 4

---
*Phase: 04-web-app-and-deployment*
*Completed: 2026-03-17*
