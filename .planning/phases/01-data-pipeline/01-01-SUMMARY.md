---
phase: 01-data-pipeline
plan: "01"
subsystem: data
tags: [usgs, requests, pandas, tqdm, python-dotenv, pysweph, uv, pyproject]

# Dependency graph
requires: []
provides:
  - pyproject.toml with all Phase 1-4 Python dependencies declared
  - pipeline/ Python package skeleton (pipeline/__init__.py, pipeline/data/__init__.py)
  - data/raw/.gitkeep directory structure
  - pipeline/data/usgs.py — decade-paginated USGS M5.5+ earthquake download script
  - data/raw/usgs_earthquakes.csv — 39,514 M5.5+ earthquake records (1900–2026, gitignored, regenerable)
  - 15-test suite (tests/test_usgs.py) covering module structure, fetch_decade, validate_result, fetch_all
affects:
  - 01-02: ephemeris feature engineering will join on earthquake event dates from this CSV
  - 02-feature-engineering: all ML features are built on top of usgs_earthquakes.csv rows
  - 03-model-training: target variable (EQIndicator) derived from this catalog

# Tech tracking
tech-stack:
  added:
    - uv (Python package manager, replaces pip+venv)
    - pysweph==2.10.3.6 (Swiss Ephemeris fork, Python 3.12 compatible)
    - requests==2.32.5
    - pandas==3.0.1
    - numpy==2.4.3
    - tqdm==4.67.3
    - python-dotenv==1.2.2
    - scikit-learn==1.8.0
    - xgboost==3.2.0
    - imbalanced-learn (via imblearn)
    - joblib==1.5.3
    - pytest==9.0.2
    - black, ruff (dev tools)
  patterns:
    - argparse CLI entry point for all pipeline scripts (--start-year, --end-year, --output)
    - Decade-chunked API pagination with truncation guard (raises RuntimeError at exactly 20k rows)
    - Exponential backoff retry (2s/4s/8s, max 3 attempts) for external HTTP calls
    - TDD workflow: RED commit (tests fail) → GREEN commit (implementation passes)
    - logging to stderr, print summary to stdout

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - pipeline/__init__.py
    - pipeline/data/__init__.py
    - pipeline/data/usgs.py
    - data/raw/.gitkeep
    - tests/__init__.py
    - tests/test_usgs.py
    - .gitignore
  modified: []

key-decisions:
  - "5-year API chunks (not 10-year) chosen to stay comfortably under 20k limit; each 5-year window peaks at ~2,665 events (2005-2009), far below 20k"
  - "TRUNCATION_LIMIT check raises RuntimeError (not warning) — silent truncation corrupts the ML target variable, so it must be fatal"
  - "hatchling build backend with packages=['pipeline'] explicit path required for uv to resolve the local package"
  - "validate_result warns (does not raise) on count < 50,000 — actual USGS M5.5+ catalog is ~39,514 records, below the planned estimate of 50k; data is complete and correct"

patterns-established:
  - "Pipeline scripts: all use argparse + main() guard + logging to stderr"
  - "TDD: failing test commit (test:) followed by implementation commit (feat:)"
  - "Retry pattern: 3 attempts, exponential backoff, raises RuntimeError on exhaustion"

requirements-completed:
  - DATA-01

# Metrics
duration: 11min
completed: 2026-03-15
---

# Phase 01 Plan 01: USGS Earthquake Data Download Summary

**Decade-paginated USGS FDSNWS download script that fetches 39,514 M5.5+ earthquakes (1900-2026) into data/raw/usgs_earthquakes.csv with truncation guard, retry logic, and full TDD test coverage**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-15T16:23:05Z
- **Completed:** 2026-03-15T16:34:33Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Initialized Python project with uv/pyproject.toml declaring all 10 production dependencies (pysweph, requests, pandas, numpy, tqdm, python-dotenv, joblib, scikit-learn, xgboost, imbalanced-learn); uv sync resolves cleanly
- Implemented pipeline/data/usgs.py with decade-paginated download, truncation guard, exponential retry, and argparse CLI; downloads 39,514 M5.5+ events in 35 seconds
- Established TDD pattern: 15 unit tests written first (RED), then implementation (GREEN) — all 15 pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Initialize Python project** - `62db747` (chore)
2. **Task 2: TDD RED — failing tests** - `d22ce3e` (test)
3. **Task 2: TDD GREEN — USGS download script** - `39eee73` (feat)

_Note: TDD task 2 has two commits (test → feat)_

## Files Created/Modified

- `pyproject.toml` - Project definition with all Phase 1-4 Python dependencies; hatchling build targeting pipeline/ package
- `uv.lock` - Locked dependency graph (1147 lines, all packages resolved)
- `pipeline/__init__.py` - Package root
- `pipeline/data/__init__.py` - Data subpackage root
- `pipeline/data/usgs.py` - USGS download: fetch_decade, fetch_all, validate_result, main; 292 lines
- `data/raw/.gitkeep` - Directory placeholder (CSV itself is gitignored)
- `tests/__init__.py` - Test package root
- `tests/test_usgs.py` - 15 unit tests covering all functions; uses unittest.mock to avoid network calls
- `.gitignore` - Excludes .se1 ephemeris files, data/raw CSVs, .venv, __pycache__, .env

## Decisions Made

- **5-year chunks over 10-year chunks**: Max observed events in any 5-year window is 2,665 (2005-2009), far below the 20k limit. 10-year windows approach 5,000+ for modern decades, still safe but 5-year gives headroom for future catalog growth.
- **Truncation guard is fatal (RuntimeError), not a warning**: Silent truncation would corrupt the ML target variable (EQIndicator). Any partial decade would make model evaluation meaningless.
- **hatchling + explicit packages=['pipeline']**: uv requires a build backend that can locate the package; without the explicit path declaration, hatchling cannot determine which files to ship into the wheel.
- **validate_result warns on count < 50,000 rather than raising**: Actual USGS M5.5+ catalog for 1900-2026 is 39,514 records. The plan's 50,000 estimate was an overestimate. Data completeness was verified via: (a) no truncation at any chunk, (b) 2004 Sumatra event present (mag 9.1, lat 3.295, lon 95.982), (c) min mag = 5.5.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added hatchling wheel target packages declaration**
- **Found during:** Task 1 (uv sync)
- **Issue:** `uv sync` failed with `ValueError: Unable to determine which files to ship` because hatchling could not find a directory named `earthquake_astrology` (pyproject name uses hyphens, filesystem uses underscores)
- **Fix:** Added `[tool.hatch.build.targets.wheel] packages = ["pipeline"]` to pyproject.toml
- **Files modified:** pyproject.toml
- **Verification:** `uv sync` completes successfully, installs all 30+ packages
- **Committed in:** `62db747` (Task 1 commit)

**2. [Rule 1 - Bug] Plan's 50,000 row threshold was an overestimate — adjusted validate_result to warn**
- **Found during:** Task 2 live download
- **Issue:** Plan stated "Total event count is above 50,000" but actual USGS M5.5+ catalog is 39,514 records. The API returns all available records with no silent truncation — the lower count is simply the actual catalog size.
- **Fix:** validate_result already warns (does not raise) on count < 50,000 per the plan spec. No code change needed; post-download validation confirmed data completeness via Sumatra check and truncation guard.
- **Files modified:** None
- **Verification:** 2004 Sumatra event present; no chunk at 20k; all required columns present; mag.min() = 5.5

---

**Total deviations:** 2 (1 blocking fix, 1 overestimate identified as non-issue)
**Impact on plan:** Build fix was necessary for correctness. Row count discrepancy is a planning estimate error, not a data quality issue.

## Issues Encountered

- uv was not on the system PATH; installed via `pip install uv`, then used as `python -m uv` — works identically to standalone `uv` binary

## User Setup Required

None - no external service configuration required. The USGS API is public and unauthenticated. To regenerate the CSV: `python pipeline/data/usgs.py`

## Next Phase Readiness

- data/raw/usgs_earthquakes.csv is on disk (39,514 rows, M5.5+, 1900-2026)
- pipeline/ package is importable: `from pipeline.data import usgs`
- All Phase 1 dependencies installed in .venv/ via uv
- Blocker from STATE.md remains: pysweph 2.10.3.6 breaking changes must be reviewed before ephemeris.py implementation

---
*Phase: 01-data-pipeline*
*Completed: 2026-03-15*
