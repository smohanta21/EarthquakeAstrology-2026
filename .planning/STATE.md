# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-14)

**Core value:** Accurate prediction of high-risk earthquake dates and regions for 2026 using astrological planetary patterns — trained on 100 years of data, validated on 26 years of out-of-sample events.
**Current focus:** Phase 1 — Data Pipeline

## Current Position

Phase: 1 of 4 (Data Pipeline)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-03-14 — Roadmap created

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: none yet
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Setup]: Use pysweph 2.10.3.6 (not pyswisseph — unmaintained since mid-2025, no Python 3.12 wheels)
- [Setup]: Pre-computed predictions only — Python ML never runs on Vercel; only static predictions.json is deployed
- [Setup]: Train on 1900–2000, test on 2000–2026 for clean temporal holdout with no data leakage

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: pysweph 2.10.3.6 has breaking changes from pyswisseph 2.10.3.2 — migration guide must be reviewed before ephemeris.py implementation begins
- [Phase 2]: Existing notebooks contain 265–309 feature columns; a column-by-column audit against the Archive notebooks is required before feature engineering planning to avoid underestimating complexity
- [Phase 3]: Model performance on 2000–2026 holdout is unknown; if F1/MCC is poor, the methodology page's model accuracy card may undermine credibility

## Session Continuity

Last session: 2026-03-14
Stopped at: Roadmap created — ready to plan Phase 1
Resume file: None
