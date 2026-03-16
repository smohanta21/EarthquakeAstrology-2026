---
phase: 02-feature-engineering
verified: 2026-03-16T15:30:00Z
status: gaps_found
score: 3/4 must-haves verified
re_verification: false
gaps:
  - truth: "data/processed/feature_matrix_test.parquet exists and is readable by pd.read_parquet()"
    status: failed
    reason: "Test parquet has a valid PAR1 header (data was written) but is missing the closing footer bytes. The file is 1.5 MB instead of the expected ~8.5 GB. ParquetWriter.close() did not execute, leaving the file in a corrupted state. pd.read_parquet() raises an exception; only raw pyarrow.parquet.ParquetFile with partial row-group reads fails gracefully."
    artifacts:
      - path: "data/processed/feature_matrix_test.parquet"
        issue: "Missing parquet footer: last 4 bytes are 0x02000000, not b'PAR1'. File contains only partial data from the first year written by ParquetWriter before the process was interrupted. All post-2000 holdout evaluation in Phase 3 is blocked until this file is regenerated."
    missing:
      - "Re-run `python pipeline/features/engineering.py` on the machine where data/raw/ephemeris.csv and data/raw/usgs_earthquakes.csv are available to regenerate feature_matrix_test.parquet with a properly closed footer."
human_verification:
  - test: "Re-run pipeline to validate test parquet"
    expected: "data/processed/feature_matrix_test.parquet is ~8.5 GB (or compressed equivalent), has PAR1 footer, and contains ~8.5M rows covering all post-2000 dates x 901 active cells with min(date) >= 2000-01-01."
    why_human: "Raw input files (ephemeris.csv, usgs_earthquakes.csv) are not present in the current environment. The pipeline cannot be re-run here to regenerate the test parquet."
---

# Phase 2: Feature Engineering Verification Report

**Phase Goal:** Separate deterministic train/test parquet files exist covering 1900-2026 with ~836 feature columns, correctly encoded, with all scalers/encoders fit exclusively on pre-2000 data, and output to data/processed/
**Verified:** 2026-03-16T15:30:00Z
**Status:** gaps_found — training parquet and all encoding artifacts are fully valid; test parquet is corrupted and blocks Phase 3 holdout evaluation
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (derived from Phase 2 Success Criteria in ROADMAP.md)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Running `python pipeline/features/engineering.py` produces `data/processed/feature_matrix_train.parquet` (~263K rows, pre-2000 downsampled 10:1) with all required columns | VERIFIED | Train parquet: 263,681 rows x 818 cols. EQIndicator: {0: 239,710, 1: 23,971}. Max date: 1999-12-31. |
| 2 | Running `python pipeline/features/engineering.py` produces `data/processed/feature_matrix_test.parquet` (~8.5M rows, post-2000 not downsampled) | FAILED | File exists (1.5 MB) but has invalid footer (last 4 bytes: `\x02\x00\x00\x00`, not `PAR1`). ParquetWriter.close() did not execute. pd.read_parquet() raises; pyarrow cannot read the file. |
| 3 | All cyclical features are encoded as sin/cos pairs — no raw integer degree, sign_num, or nakshatra_num columns remain | VERIFIED | Train parquet: all {p}_lon_sin/cos, {p}_sign_num_sin/cos, {p}_nakshatra_num_sin/cos, tithi_sin/cos present. Zero columns ending with bare `_lon`, `_sign_num`, `_nakshatra_num`, or `_sign` found. |
| 4 | Temporal split enforced: max(train.date) < 2000-01-01; OneHotEncoder fit exclusively on pre-2000 rows | VERIFIED | Train max date: 1999-12-31. Encoder fit on pre-2000 ephemeris rows only (confirmed in main() Step 2). assert_no_temporal_leakage() is a hard AssertionError guard. |

**Score:** 3/4 truths verified (test parquet corrupted)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `data/processed/feature_matrix_train.parquet` | Pre-2000 training matrix, ~263K rows, 10:1 downsampled | VERIFIED | 263,681 rows x 818 cols, 36.6 MB, valid PAR1 footer |
| `data/processed/feature_matrix_test.parquet` | Post-2000 test matrix, ~8.5M rows, NOT downsampled | CORRUPTED | 1.5 MB (partial), PAR1 header present but footer missing — `\x02\x00\x00\x00` instead of `PAR1` |
| `data/processed/feature_columns.json` | Ordered list of 813 ML feature column names for Phase 3 | VERIFIED | 813 feature columns, valid JSON list of strings, excludes EQIndicator/grid_lat/grid_lon/country/date meta-columns |
| `data/processed/nakshatra_encoder.pkl` | Fitted OneHotEncoder, pre-2000 vocabulary only | VERIFIED | joblib.load() succeeds; isinstance(enc, OneHotEncoder) = True; 13 planet features; InconsistentVersionWarning (fit on sklearn 0.24.1, current env is 1.8.0 — functional) |
| `pipeline/features/engineering.py` | main() orchestration function wiring all steps | VERIFIED | 799-line module; main() implements all 10 steps; if __name__ == '__main__': main() present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `main()` | `data/processed/feature_matrix_train.parquet` | `pd.concat of per-year downsampled chunks -> to_parquet(engine='pyarrow', compression='snappy')` | VERIFIED | train_df.to_parquet() at line 741; snappy compression confirmed |
| `main()` | `data/processed/feature_matrix_test.parquet` | `ParquetWriter.write_table() per year + writer.close()` | PARTIAL | Code correctly calls writer.close() at line 765. File is corrupted because a prior run was interrupted before close() executed; the current code is correct. |
| `fit_nakshatra_encoder()` | pre-2000 ephemeris rows | `ephe_df.loc[ephe_df.index < pd.Timestamp('2000-01-01')]` before encode_ephemeris | VERIFIED | Step 2 in main() filters to pre-2000 before calling fit_nakshatra_encoder() |
| `assert_no_temporal_leakage()` | Hard temporal boundary enforcement | `AssertionError` on max(train) >= 2000-01-01 | VERIFIED | Line 732 in main(); raises AssertionError with date in message; 55/57 tests pass |
| `build_eq_index()` | EQIndicator assignment in build_matrix_year() | `eq_index.reindex(MultiIndex).fillna(0).astype(int)` | VERIFIED | Confirmed in engineering.py lines 621-629; test TestEQIndicatorCollapse confirms no duplicates |
| `data/processed/feature_columns.json` | Phase 3 model training | `json.dump of [c for c in train_df.columns if c not in meta_cols]` | VERIFIED | 813 column names; no meta-columns included |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| FEAT-01 | 02-01, 02-02, 02-03 | Feature matrix with planetary degrees, retrograde flags, zodiac signs, aspects, nakshatras matching ~265-column structure | SATISFIED | Train parquet has 813 feature cols: 26 lon sin/cos, 26 sign_num sin/cos, 26 nak_num sin/cos, 13 retro, 390 aspect booleans, 2 tithi, 330 nakshatra OHE. Note: 330 OHE cols (not 351) because Neptune traversed only 18 and Pluto only 15 nakshatras in pre-2000 era — correct encoder-fit behavior. |
| FEAT-02 | 02-01, 02-03 | Cyclical sin/cos encoding for degrees 0-360, signs 1-12, nakshatras 1-27 | SATISFIED | encode_cyclic() uses `series * (2*pi/period)`. TestCyclicalEncoding: sun_lon=0 gives sin=0/cos=1; sun_lon=90 gives sin~1/cos~0. No raw _lon, _sign_num, _nakshatra_num columns in output parquet. |
| FEAT-03 | 02-01, 02-04 | Train/test split at 2000-01-01; all scalers/encoders fit exclusively on pre-2000 data | SATISFIED (train) / BLOCKED (test) | Encoder fit on pre-2000 rows (verified). Train max date: 1999-12-31. assert_no_temporal_leakage() is a hard AssertionError. Test parquet must be regenerated to verify post-2000 holdout boundary. |
| FEAT-04 | 02-01, 02-02 | EQIndicator target variable: 1 for M5.5+ earthquake dates, 0 for non-earthquake dates | SATISFIED | Train parquet EQIndicator: {0: 239,710, 1: 23,971}. Both classes present. build_eq_index collapses duplicate (date, cell) pairs to single value 1. TestEQIndicatorCollapse passes. |
| FEAT-05 | 02-01, 02-02 | Regional geographic identifiers (country, lat/long grid cell) as prediction dimensions | SATISFIED | Train parquet contains grid_lat, grid_lon, country columns. Grid cells are 5x5 floor-division buckets. build_country_map assigns most-common country per cell. 901 active cells discovered from full USGS catalog. |

All 5 FEAT requirements (FEAT-01 through FEAT-05) are covered by the 5 plans in this phase. No orphaned requirements found.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `data/processed/feature_matrix_test.parquet` | N/A (file artifact) | Corrupted parquet — missing footer bytes | BLOCKER | Phase 3 holdout evaluation (2000-2026 test set) cannot run until test parquet is regenerated. The code is correct; this is a prior-run interruption artifact. |
| `data/processed/nakshatra_encoder.pkl` | N/A (file artifact) | Serialized with sklearn 0.24.1, current env is 1.8.0 — InconsistentVersionWarning on load | WARNING | joblib.load() succeeds and encoder is functional. Phase 3 should re-fit or re-save the encoder with current sklearn to eliminate the warning and ensure serialization stability. |

No code-level anti-patterns found in engineering.py (no TODO/FIXME/placeholder comments, no empty implementations, no console.log-only handlers).

### Column Count Note (813 vs ~836 in roadmap)

The roadmap goal states "~836 feature columns." The actual feature column count is 813 (818 total including 5 meta-columns). The difference of 21 columns is fully explained:

- Plan 03 projected 351 nakshatra OHE columns (13 planets x 27 nakshatras)
- Actual: 330 OHE columns because Neptune traversed only 18 distinct nakshatras and Pluto only 15 in the pre-2000 training era (slow outer planets with 165/248-year orbital periods)
- This is correct FEAT-03 behavior: the encoder is fit only on pre-2000 data and cannot add categories for nakshatras those planets never reached during training
- The `~` in the roadmap goal explicitly acknowledges approximation; 813 falls within reasonable tolerance of 836

### Human Verification Required

#### 1. Regenerate Test Parquet

**Test:** On the machine where `data/raw/ephemeris.csv` and `data/raw/usgs_earthquakes.csv` exist, run `python pipeline/features/engineering.py` to completion.
**Expected:**
- `data/processed/feature_matrix_test.parquet` has a valid PAR1 footer
- File is ~8-10 GB (or compressed equivalent with snappy)
- `pd.read_parquet('data/processed/feature_matrix_test.parquet', columns=['date']).min()` returns a date >= 2000-01-01
- After regeneration, `pytest tests/test_engineering.py -v` shows 57 passed, 0 skipped
**Why human:** Raw input files are not available in this environment. The pipeline cannot be re-run here.

### Gaps Summary

The phase has one blocking gap: `feature_matrix_test.parquet` is corrupted. All training artifacts are fully valid and Phase 3 model training can proceed using the training parquet, but Phase 3 holdout evaluation on the 2000-2026 test set is blocked until the test parquet is regenerated.

The root cause is a prior pipeline run being interrupted after ParquetWriter began writing but before `writer.close()` was called. The code is correct — `writer.close()` is present at line 765 in engineering.py and is guarded by `if writer:`. The fix is purely operational: re-run the pipeline on the machine with raw data.

All other phase deliverables are complete and wired:
- Training parquet: 263,681 rows, correct temporal split, all 813 feature columns, no raw columns
- feature_columns.json: 813 ML feature names, valid JSON, excludes meta-columns
- nakshatra_encoder.pkl: functional OneHotEncoder with 13-planet vocabulary fit on pre-2000 data
- engineering.py: all 10+ functions implemented, tested, and wired through main()
- Test suite: 55 passed, 2 skipped (both skips are the test parquet tests, expected given corruption)

---
_Verified: 2026-03-16T15:30:00Z_
_Verifier: Claude (gsd-verifier)_
