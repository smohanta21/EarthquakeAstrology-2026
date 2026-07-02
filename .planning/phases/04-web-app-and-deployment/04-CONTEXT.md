# Phase 4: Web App and Deployment - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a Next.js app in the `web/` directory that reads `web/public/data/predictions.json` at build time (Server Component — no client-side fetch), displays 2026 earthquake risk predictions as an interactive calendar for March–December, and deploys to Vercel. Python ML pipeline is complete and out of scope. The `predictions.json` artifact already exists at `web/public/data/predictions.json`.

</domain>

<decisions>
## Implementation Decisions

### Calendar Layout
- All 10 months (March–December 2026) displayed on a single scrollable page — no navigation controls needed
- Standard calendar grid: each date is a cell with the date number in the corner; no text inside cells
- Cell background color = risk tier (binary: normal or high-risk)
- Plain white/neutral cells for dates with no predictions above threshold

### Risk Tiers
- **2 tiers only (binary):** Normal (white/neutral) vs High-risk (colored)
- A date is high-risk if `predictions.json` has any entry for that date above the stored threshold
- No further subdivision into medium/low/high — a date either has a prediction or it doesn't

### Date Detail Panel
- **Slide-in side panel from the right** when clicking a high-risk date
- Calendar stays visible on the left while panel is open
- Panel contents:
  - Risk score (numeric, e.g., 0.73 — or a visual bar alongside the number)
  - All predicted region(s) for that date, listed and sorted by `risk_score` descending (show all, not capped)
  - Each region entry: country name + lat/lon grid cell (e.g., "Indonesia — lat -5, lon 110")
  - Top planetary aspects (the `top_planetary_aspects` array from predictions.json — typically 3 strings)
- Panel closes when user clicks outside it or clicks another date

### Click Behavior on Normal Dates
- Clicking a white/neutral (no-prediction) date **highlights all high-risk dates in that same week** — gives the user risk context for the surrounding week without a detail panel
- High-risk dates in that week get a visual highlight (e.g., ring or outline) that clears on the next interaction

### Disclaimer (WEB-04)
- A prominent scientific disclaimer must be visible on the main page without any user interaction
- Claude's discretion on exact placement and styling (e.g., static banner below the page header, or above the calendar grid) — must not be dismissable or hidden behind any toggle

### Methodology Page (WEB-03)
- Reachable from the calendar page (e.g., nav link or footer link)
- Must display model evaluation metrics from `data/models/eval_report.json`:
  - Model used: XGBClassifier
  - F1 score: 0.002774
  - MCC: 0.001363
  - Confusion matrix (TP, FP, FN, TN) for 2010–2026 holdout period
  - Eval split date: 2010-01-01
- Claude's discretion on layout and depth of explanation (description of astrological features, training data, approach)

### Build-Time Data Loading (WEB-05)
- Next.js Server Component reads `predictions.json` at build time — no `fetch()` or client-side data loading
- `predictions.json` stays in `web/public/data/` and is served as a static asset — NOT imported into the serverless function bundle

### Claude's Discretion
- Color choice for high-risk cells (e.g., red, amber, orange)
- Typography, spacing, and exact styling
- Mobile/responsive layout
- Week highlight visual treatment (ring, outline, background)
- Methodology page explanation depth and prose
- Disclaimer exact wording beyond the required content (must state: experimental model, earthquakes cannot be reliably predicted)
- Next.js version and specific package choices (e.g., Tailwind vs CSS modules)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Web UI (WEB-01 through WEB-05) — calendar view, detail panel, methodology page, disclaimer, Server Component data loading
- `.planning/REQUIREMENTS.md` §Deployment (DEPLOY-01, DEPLOY-02) — Vercel deployment from `web/`, predictions.json in `public/data/`

### Data Artifacts (inputs to Phase 4)
- `web/public/data/predictions.json` — 901 prediction entries, March–December 2026. Schema per entry: `date` (ISO string), `country`, `lat`, `lon`, `risk_score` (float 0–1), `top_planetary_aspects` (array of ≤3 strings)
- `data/models/eval_report.json` — model evaluation metrics for methodology page: `model_used`, `f1_score`, `mcc`, `confusion_matrix`, `threshold`, `eval_split_date`, `both_models`

No external design specs or ADRs — all requirements are captured in REQUIREMENTS.md and this context file.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `web/public/data/predictions.json`: Already committed — Phase 4 reads this at build time; no re-generation needed
- `data/models/eval_report.json`: Already committed — methodology page reads these values directly

### Established Patterns
- Python pipeline uses `.venv` + `uv` — web app is separate (`web/` directory) and uses its own Node.js package manager
- No existing Next.js app files yet — `web/` only contains `public/data/` subdirectory

### Integration Points
- Phase 4 creates `web/` as a Next.js project root
- `web/public/data/predictions.json` is the only data dependency from earlier phases
- `data/models/eval_report.json` is read at build time for the methodology page (copy to `web/public/data/` or import directly in Server Component — Claude's discretion)
- Vercel deployment configured from the `web/` directory (not repo root)

</code_context>

<specifics>
## Specific Ideas

- The model's F1 and MCC scores are very low (0.002774 and 0.001363 respectively) — the methodology page and disclaimer should be honest about model limitations; this is an experimental project, not a validated forecasting tool
- WEB-04 disclaimer: must state the app is experimental and earthquakes cannot be reliably predicted — this needs to be immediately visible without scrolling or interaction

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-web-app-and-deployment*
*Context gathered: 2026-03-17*
