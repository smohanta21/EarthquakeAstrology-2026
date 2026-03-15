---
phase: 02-feature-engineering
plan: "02"
subsystem: feature-engineering
tags: [grid-cells, usgs-preprocessing, eq-index, country-map, tdd]
dependency_graph:
  requires: [02-01]
  provides: [compute_grid_coords, build_active_cells, extract_country, build_eq_index, build_country_map]
  affects: [02-03, 02-04]
tech_stack:
  added: []
  patterns: [vectorized-numpy-floor, object-dtype-multiindex, drop-duplicates-collapse]
key_files:
  created: []
  modified:
    - pipeline/features/engineering.py
    - tests/test_engineering.py
decisions:
  - "object-dtype date index: pd.Index(dates, dtype=object) used for MultiIndex date level to preserve datetime.date type and prevent pandas coercion to DatetimeIndex, which breaks dict-key lookups"
  - "tolist() for numpy int conversion: .astype(int).tolist() used to ensure Python native int in tuples, not numpy.int64, so isinstance(x, int) assertions pass"
metrics:
  duration_minutes: 4
  completed_date: "2026-03-15"
  tasks_completed: 2
  files_modified: 2
---

# Phase 2 Plan 02: USGS Grid and EQ Index Functions Summary

**One-liner:** USGS preprocessing pipeline — 5-degree grid cell mapping, EQ MultiIndex with date-collapse, and country map using vectorized numpy floor with object-dtype date preservation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement grid cell and active cells functions | adec351 | pipeline/features/engineering.py, tests/test_engineering.py |
| 2 | Implement country extraction, EQ index, and country map | 1db18cb | pipeline/features/engineering.py, tests/test_engineering.py |

## What Was Built

### compute_grid_coords
Maps a (lat, lon) coordinate to the nearest 5-degree grid cell using `int(np.floor(x/5)*5)`. Handles negative latitudes correctly (e.g., lat=-3.0 maps to grid_lat=-5, not -0 or 0).

### build_active_cells
Vectorized numpy floor operation across the entire USGS DataFrame. Returns a set of Python int tuples. Verified against full USGS dataset: 901 active cells across 1900-2026.

### extract_country
Handles all USGS place field edge cases: None, float NaN, empty string all return "Unknown". Last comma-delimited token returned for normal place strings.

### build_eq_index
Returns a `pd.Series` with MultiIndex `(date, grid_lat, grid_lon)` where all values are 1. Multiple USGS events on the same date in the same 5-degree cell are collapsed to a single entry via `drop_duplicates`. Date level stored as `datetime.date` objects (not Timestamps) using `pd.Index(dates, dtype=object)`.

### build_country_map
Groups USGS events by grid cell and assigns the most common country label per cell. Returns a dict of `(int, int) -> str` mappings for use in Plan 04's matrix builder.

## Test Results

```
16 passed, 15 xfailed
```

- TestGridCells: 6 tests pass (basic, negative lat, zero, Japan region, set-of-tuples, known values)
- TestCountryParsing: 6 tests pass (standard, no-comma, None, empty, NaN, Alaska multi-comma)
- TestEQIndicator: 3 tests pass (returns Series, MultiIndex structure, value-is-1 lookup)
- TestEQIndicatorCollapse: 1 test pass (two events same cell same date -> single entry)
- Remaining xfail tests: unchanged from Plan 01 scaffold (Wave 2 scope)

## Smoke Test

```
Active cells: 901
```

Matches the plan specification exactly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed numpy int type in build_active_cells**
- **Found during:** Task 1 GREEN phase — test_build_active_cells_returns_set_of_tuples failed on `isinstance(cell[0], int)`
- **Issue:** `np.floor(...).astype(int)` produces `numpy.int64` not Python `int`; `isinstance(numpy.int64, int)` is False in Python 3.8
- **Fix:** Used `.tolist()` to convert numpy array to Python native ints before `zip()`
- **Files modified:** pipeline/features/engineering.py
- **Commit:** adec351

**2. [Rule 1 - Bug] Fixed datetime.date coercion in build_eq_index MultiIndex**
- **Found during:** Task 2 GREEN phase — test_build_eq_index_value_is_1 failed with KeyError
- **Issue:** pandas coerces `datetime.date` objects to `Timestamp` (DatetimeIndex) when passed as a list to `pd.MultiIndex.from_arrays()`, making `result[(datetime.date(...), 35, -125)]` fail
- **Fix:** Wrapped date list in `pd.Index(dates, dtype=object)` to force object dtype and prevent Timestamp coercion
- **Files modified:** pipeline/features/engineering.py
- **Commit:** 1db18cb

## Self-Check: PASSED

- pipeline/features/engineering.py: FOUND
- tests/test_engineering.py: FOUND
- .planning/phases/02-feature-engineering/02-02-SUMMARY.md: FOUND
- Commit efa72bc (RED Task 1): FOUND
- Commit adec351 (GREEN Task 1): FOUND
- Commit 824e03a (RED Task 2): FOUND
- Commit 1db18cb (GREEN Task 2): FOUND
