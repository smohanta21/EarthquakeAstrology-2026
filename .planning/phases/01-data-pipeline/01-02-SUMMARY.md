---
phase: 01-data-pipeline
plan: 02
subsystem: data
tags: [pysweph, swiss-ephemeris, planetary-positions, nakshatra, vedic-astrology, aspects, ephemeris-csv]

# Dependency graph
requires:
  - phase: 01-data-pipeline
    provides: pipeline structure, pyproject.toml with pysweph dependency, data/ directory layout

provides:
  - pipeline/data/ephemeris.py: Daily planetary position computation (1900-2026) using pysweph
  - data/ephe/download_ephe.sh: One-time Swiss Ephemeris data file download script (GitHub URL)
  - .env.example: Template for SE_EPHE_PATH and output path configuration
  - Tests: 25 tests covering compute_day, compute_aspects, setup_ephemeris, module structure

affects:
  - 02-feature-engineering
  - 03-model-training
  - 04-web-deployment

# Tech tracking
tech-stack:
  added:
    - pysweph 2.10.3.6 (Swiss Ephemeris Python bindings)
    - python-dotenv (SE_EPHE_PATH loading from .env)
    - tqdm (progress bars for 46k-row computation)
    - pandas (date_range generation, CSV output)
  patterns:
    - TDD: failing tests committed before implementation
    - pysweph 2.10.3.6 calc_ut returns 3-tuple (xx, iflag, serr) — must unpack all 3
    - UTC noon (hour=12.0) for all Julian Day computations
    - Lahiri ayanamsha + FLG_SIDEREAL for Vedic nakshatra; reset to tropical (set_sid_mode(0)) after each nakshatra calc
    - setup_ephemeris() must be called before any swe.calc_ut() invocation

key-files:
  created:
    - pipeline/data/ephemeris.py
    - data/ephe/download_ephe.sh
    - .env.example
    - tests/test_ephemeris.py
  modified:
    - data/ephe/download_ephe.sh (URL fix: AstroDienst FTP -> GitHub raw)

key-decisions:
  - "pysweph 2.10.3.6 calc_ut API returns 3-tuple (xx, iflag, serr) — not the 2-tuple (xx, ret) documented in pyswisseph 2.10.3.2 plan interface; unpack all 3 values"
  - "Swiss Ephemeris .se1 files now at GitHub (https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/) — AstroDienst FTP URL 404s; download script updated"
  - "Chiron (swe.CHIRON, asteroid 2060) requires seas_18.se1 — does not fall back to Moshier like other planets; file must be present for compute_day to succeed"
  - "setup_ephemeris() logs warning (not error) when .se1 files absent — Moshier fallback acceptable for planets, but seas_18.se1 required for Chiron"

patterns-established:
  - "Ephemeris computation: always call setup_ephemeris() before any swe.calc_ut() call"
  - "Julian Day: always use hour=12.0 (UTC noon) — never 0.0 (midnight)"
  - "API unpacking: xx, _iflag, _serr = swe.calc_ut(jd, planet_id)"
  - "Sidereal calc: set_sid_mode(SIDM_LAHIRI) -> calc_ut with FLG_SIDEREAL -> set_sid_mode(0)"
  - "Aspect normalization: abs((lon1 - lon2) % 360); if > 180: use 360 - diff"

requirements-completed: [DATA-02, DATA-03, DATA-04]

# Metrics
duration: 5min
completed: 2026-03-15
---

# Phase 1 Plan 2: Swiss Ephemeris Computation Script Summary

**pysweph-based daily planetary position pipeline computing longitude, sign, retrograde, Vedic nakshatra, and 390 aspect columns for 13 planets across 1900-2026**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-15T16:39:37Z
- **Completed:** 2026-03-15T16:44:19Z
- **Tasks:** 2 (+ TDD RED/GREEN commits = 4 total commits)
- **Files modified:** 4 created, 1 modified

## Accomplishments

- `pipeline/data/ephemeris.py` implemented with compute_day (13 planets x 6 columns), compute_aspects (390 binary aspect columns), setup_ephemeris, and main CLI entry point
- Full TDD cycle: 25 failing tests committed first, then implementation to pass all 25
- `data/ephe/download_ephe.sh` created for one-time ephemeris file setup; URL bug fixed (AstroDienst FTP 404 -> GitHub raw)
- `.env.example` template with SE_EPHE_PATH, USGS_OUTPUT, EPHEMERIS_OUTPUT

## Task Commits

Each task was committed atomically:

1. **Task 1: Ephemeris download script and .env setup** - `b1a62ac` (chore)
2. **Task 2 RED: Failing tests** - `ceefc9b` (test)
3. **Task 2 GREEN: Implementation** - `b90381a` (feat)

_Note: TDD task has separate test and feat commits per TDD protocol_

## Files Created/Modified

- `pipeline/data/ephemeris.py` - Daily planetary computation: compute_day, compute_aspects, setup_ephemeris, main; handles pysweph 2.10.3.6 3-tuple API
- `data/ephe/download_ephe.sh` - Downloads sepl_18.se1, semo_18.se1, seas_18.se1, sefstars.txt from GitHub
- `.env.example` - Environment template with SE_EPHE_PATH and output path vars
- `tests/test_ephemeris.py` - 25 tests: module structure (AST), compute_day, compute_aspects, setup_ephemeris

## Decisions Made

- pysweph 2.10.3.6 breaks from pyswisseph: `calc_ut` returns `(xx, iflag, serr)` 3-tuple not `(xx, ret)` 2-tuple. Implementation unpacks all three values; documented in module docstring.
- Swiss Ephemeris download URLs changed from AstroDienst FTP to GitHub. Download script updated to use `https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/`.
- Chiron strictly requires `seas_18.se1` — unlike Sun/Moon/planets, it does not silently fall back to Moshier. Downloaded `seas_18.se1` to enable tests to run without sepl/semo files.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed download_ephe.sh URL: AstroDienst FTP -> GitHub raw**
- **Found during:** Task 1 verification (after creating the script)
- **Issue:** `https://www.astro.com/ftp/swisseph/ephe/` returns 404. AstroDienst moved Swiss Ephemeris files to GitHub (aloistr/swisseph) in 2024. The FTP URL was documented in STACK.md research but the server no longer serves the files.
- **Fix:** Changed BASE_URL to `https://raw.githubusercontent.com/aloistr/swisseph/master/ephe`; added `-L` flag to curl for redirect following.
- **Files modified:** `data/ephe/download_ephe.sh`
- **Verification:** `curl -I` on GitHub URL returns 200; `seas_18.se1` downloaded successfully (217KB)
- **Committed in:** `b90381a` (Task 2 GREEN commit)

**2. [Rule 1 - Bug] Handled pysweph 2.10.3.6 breaking API change: calc_ut returns 3-tuple**
- **Found during:** Task 2 GREEN (implementation testing)
- **Issue:** Plan interface showed `xx, ret = swe.calc_ut(jd, swe.SUN)` (pyswisseph 2.10.3.2 API). pysweph 2.10.3.6 returns `(xx, iflag, serr)` — a 3-tuple. Unpacking as 2-tuple raises `ValueError: too many values to unpack`.
- **Fix:** Changed all `calc_ut` calls to unpack 3 values: `xx, _iflag, _serr = swe.calc_ut(jd, planet_id)`. Documented in module docstring and inline comments.
- **Files modified:** `pipeline/data/ephemeris.py`
- **Verification:** All 25 tests pass; smoke test shows Sun lon 280.37° on 2000-01-01 (correct Capricorn)
- **Committed in:** `b90381a` (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both fixes necessary for the script to function at all. The pysweph API change was flagged as a known risk in STATE.md blockers; the FTP URL change was undiscovered until execution.

## Issues Encountered

- pysweph 2.10.3.6 API differs from plan's pyswisseph 2.10.3.2 interface in one critical way: `calc_ut` return arity (3 vs 2 values). Fixed inline.
- Chiron (swe.CHIRON) strictly requires `seas_18.se1` and does not use Moshier fallback. Downloaded the file (217KB) so tests can run. The full sepl_18.se1 and semo_18.se1 are still needed for precision (vs Moshier) but not required for test correctness.

## User Setup Required

**Users must run this one-time setup before executing ephemeris.py:**

```bash
# 1. Download Swiss Ephemeris data files (sepl_18.se1, semo_18.se1, seas_18.se1, sefstars.txt)
bash data/ephe/download_ephe.sh

# 2. Create .env from template
cp .env.example .env

# 3. (Optional) Verify smoke test
python -c "import os; os.environ['SE_EPHE_PATH']='./data/ephe'; from pipeline.data.ephemeris import setup_ephemeris, compute_day; setup_ephemeris(); row = compute_day('2000-01-01'); print('Sun lon:', row['sun_lon'])"

# 4. Full 1900-2026 run (20-30 minutes)
python pipeline/data/ephemeris.py
```

Note: `seas_18.se1` is already present in `data/ephe/` (downloaded during plan execution). The full precision files `sepl_18.se1` and `semo_18.se1` still need to be downloaded via the script above.

## Next Phase Readiness

- `pipeline/data/ephemeris.py` ready to produce `data/raw/ephemeris.csv` once user runs setup
- User must run `bash data/ephe/download_ephe.sh` to get full precision ephemeris (sepl/semo files)
- Downstream phases (feature engineering) depend on `data/raw/ephemeris.csv` existing
- Blocker resolved: pysweph 2.10.3.6 API migration documented and implemented

---
*Phase: 01-data-pipeline*
*Completed: 2026-03-15*

## Self-Check: PASSED

- pipeline/data/ephemeris.py: FOUND
- data/ephe/download_ephe.sh: FOUND
- .env.example: FOUND
- tests/test_ephemeris.py: FOUND
- Commit b1a62ac (chore): FOUND
- Commit ceefc9b (test): FOUND
- Commit b90381a (feat): FOUND
