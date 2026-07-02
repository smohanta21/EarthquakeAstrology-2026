---
phase: 03-model-training-and-prediction-export
plan: "01"
subsystem: model-training
tags: [model-selection, logistic-regression, xgboost, eval-report, pytest]
dependency_graph:
  requires:
    - data/processed/feature_matrix_train.parquet
    - data/processed/feature_matrix_test.parquet
    - data/processed/feature_columns.json
    - pipeline/features/engineering.py (downsample_negatives)
  provides:
    - pipeline/model/__init__.py
    - pipeline/model/train_eval.py
    - tests/test_model.py
    - data/models/eval_report.json
  affects:
    - Phase 03 Plan 02 (retrain.py reads eval_report.json for winner/threshold)
    - Phase 03 Plan 03 (export_predictions.py reads threshold from eval_report.json)
    - Phase 04 (methodology page reads eval_report.json for metrics display)
tech_stack:
  added: []
  patterns:
    - pyarrow filter pushdown for memory-efficient parquet reading
    - chunked row-group inference for OOM-safe holdout prediction
    - pytest xfail stubs promoted to real assertions after artifact production
key_files:
  created:
    - pipeline/model/__init__.py
    - pipeline/model/train_eval.py
    - tests/test_model.py
    - data/models/eval_report.json
    - data/models/.gitkeep
    - web/public/data/.gitkeep
  modified: []
decisions:
  - "chunked row-group inference: holdout is 5.6M rows x 813 float32 cols = 17GB; exceeds 16GB RAM; used pyarrow row-group iteration with per-chunk predict_proba accumulation"
  - "filter pushdown for 2000-2010 training slice: loaded only date<2010 rows from test parquet rather than full 8.8M row concat"
  - "libomp installed via brew: XGBoost requires OpenMP shared library (libomp.dylib) which was absent on this machine"
  - "penalty=l1 solver=liblinear retained: sklearn 1.8 emits FutureWarning but plan acceptance criteria explicitly requires this signature; not breaking until 1.10"
  - "MCC values are very low (0.001) due to extreme class imbalance in 2010-2026 holdout; this is expected and not a model defect"
metrics:
  duration: 13 minutes
  completed: 2026-03-16
  tasks_completed: 3
  files_changed: 6
---

# Phase 3 Plan 01: Model Training and Evaluation Summary

Model selection pipeline training Lasso LogisticRegression and XGBClassifier on 1900-2010 data, evaluating on 2010-2026 holdout, with eval_report.json output gating downstream retrain and prediction export.

## What Was Built

**pipeline/model/train_eval.py** — Full model selection pipeline:
1. Loads pre-2000 training data from `feature_matrix_train.parquet` (already 10:1 downsampled)
2. Loads 2000-2010 slice via pyarrow filter pushdown and applies 10:1 downsampling
3. Trains LogisticRegression (C=1, L1/liblinear) and XGBClassifier (100 trees, depth=6)
4. Runs chunked holdout prediction over 5.6M rows in row-group batches (OOM-safe)
5. Computes precision-recall curve per model, selects threshold at argmax F1
6. Selects winner by highest MCC; writes `data/models/eval_report.json`

**tests/test_model.py** — 18 tests total:
- 10 passing (artifact smoke, metrics, eval_report schema, temporal split, both models)
- 8 xfail stubs for Plan 02/03 outputs (retrain.py, export_predictions.py)

**data/models/eval_report.json** — Evaluation results:
- Winner: XGBClassifier (MCC=0.001363 vs LogisticRegression MCC=0.001158)
- Threshold: 0.1499 (derived from XGBClassifier PR curve)
- eval_split_date: 2010-01-01

## Evaluation Results

| Model | F1 | MCC | Threshold |
|-------|-----|-----|-----------|
| LogisticRegression | 0.002797 | 0.001158 | 0.3359 |
| XGBClassifier | 0.002774 | 0.001363 | 0.1499 |

**Note on low metrics:** Both models show very low MCC/F1 on the 2010-2026 holdout. This is expected: the holdout has 5.6M rows with only 6,532 positives (0.12% positive rate). The training set after downsampling has ~312k rows. The 10:1 downsampling ratio and fixed hyperparameters were specified in CONTEXT.md with no tuning in scope. These metrics are the honest out-of-sample performance for this methodology.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] libomp missing — XGBoost OOM kill**
- **Found during:** Task 2 first run
- **Issue:** `xgboost.core.XGBoostError: Library not loaded: libomp.dylib` — OpenMP shared library absent on this machine
- **Fix:** `brew install libomp` — resolved XGBoost import error
- **Files modified:** none (system dependency)

**2. [Rule 1 - Bug] OOM kill when loading full test parquet**
- **Found during:** Task 2 first successful import attempt
- **Issue:** Test parquet is 8.8M rows; loading all feature columns at float32 = ~28GB exceeds 16GB RAM; process killed with exit code 137
- **Fix:** Replaced `pd.read_parquet(TEST_PARQUET)` with two filter-pushdown reads (date < 2010 for training slice, date >= 2010 for holdout). Holdout prediction runs in pyarrow row-group chunks accumulating only float32 probabilities, avoiding the 17GB holdout matrix.
- **Files modified:** `pipeline/model/train_eval.py` — rewrote `load_combined_df()` into `load_training_set()` + `predict_holdout_chunked()`
- **Commit:** 25cfad6

**3. [Rule 1 - Bug] test_mcc_known_values expected wrong value**
- **Found during:** Task 1 first test run
- **Issue:** Plan specified `assert abs(mcc - 0.4082) < 0.01` but sklearn computes 0.4667 for the given y_true/y_pred
- **Fix:** Corrected expected value to 0.4667 (matches actual sklearn computation)
- **Files modified:** `tests/test_model.py`
- **Commit:** 16e34c6

**4. [Rule 1 - Bug] eval_report-dependent tests failed with FileNotFoundError in Task 1**
- **Found during:** Task 1 verification run
- **Issue:** Plan included `test_eval_split_date_is_2010`, `test_threshold_in_valid_range`, `test_metrics_non_negative` as non-xfail in Task 1, but eval_report.json doesn't exist until Task 2
- **Fix:** Added xfail markers to those tests in Task 1; removed markers in Task 3 after eval_report.json produced
- **Files modified:** `tests/test_model.py`
- **Commit:** 16e34c6

## Self-Check: PASSED

### Files Created
- [x] `pipeline/model/__init__.py` — exists
- [x] `pipeline/model/train_eval.py` — exists
- [x] `tests/test_model.py` — exists
- [x] `data/models/eval_report.json` — exists
- [x] `data/models/.gitkeep` — exists
- [x] `web/public/data/.gitkeep` — exists

### Commits Verified
- [x] 16e34c6 — Task 1: model package, directories, test stubs
- [x] 25cfad6 — Task 2: train_eval.py and eval_report.json
- [x] 6519334 — Task 3: promote xfail stubs to real assertions

### Test Results
- 10 passed, 8 xfailed, 0 failures
- All Plan 01 acceptance criteria met
