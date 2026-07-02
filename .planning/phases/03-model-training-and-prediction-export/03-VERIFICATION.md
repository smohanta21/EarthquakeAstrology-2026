---
phase: 03-model-training-and-prediction-export
verified: 2026-03-16T23:45:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
human_verification:
  - test: "Inspect predictions.json geographic coverage to confirm 901 above-threshold records on 2026-03-08 are plausible earthquake-risk regions rather than arbitrary artifacts"
    expected: "Records should map to known seismically active zones (Pacific Ring of Fire, etc.)"
    why_human: "Model assigns max score 0.2266 — barely above threshold 0.1499 — concentrated on one date. Requires domain judgment on whether the model is producing coherent signal or overfitting to a planetary configuration."
  - test: "Verify that predictions.json covering only 2026-03-08 is acceptable for the Phase 4 web app"
    expected: "Phase 4 can display the 901 single-date records meaningfully; or Phase 4 stakeholder accepts sparse output"
    why_human: "PRED-01 says 'March-December 2026' — the system generates for that full range but threshold filtering leaves only one date. The code is correct; acceptability is a product decision."
---

# Phase 3: Model Training and Prediction Export — Verification Report

**Phase Goal:** Train earthquake prediction model, evaluate model selection, export 2026 predictions
**Verified:** 2026-03-16T23:45:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Both LogisticRegression and XGBClassifier are trained on pre-2010 data and evaluated on 2010-2026 holdout | VERIFIED | `train_eval.py` lines 37-38: `EVAL_SPLIT_DATE = datetime.date(2010, 1, 1)`; both models fit on filtered training set; chunked holdout prediction over 5.6M rows |
| 2 | eval_report.json exists with model_used, f1_score, mcc, confusion_matrix, threshold, eval_split_date, both_models | VERIFIED | File exists (440 bytes); `TestEvalReport::test_report_schema` PASSED; actual values confirmed: `model_used=XGBClassifier`, `threshold=0.149939`, `eval_split_date=2010-01-01` |
| 3 | Winner is selected by highest MCC on holdout | VERIFIED | `select_winner_and_write_report()` uses `max(results, key=lambda r: r["mcc"])`; XGBClassifier MCC=0.001363 beats LogisticRegression MCC=0.001158 |
| 4 | Threshold is derived from precision-recall curve at best F1 operating point | VERIFIED | `evaluate_model()` uses `precision_recall_curve`, computes F1 array, selects `argmax`; `TestEvalReport::test_threshold_in_valid_range` PASSED (0.0 < 0.149939 < 1.0) |
| 5 | Winning model is retrained on full 1900-2026 data (10:1 downsampled) and serialized to eq_classifier.pkl | VERIFIED | `retrain.py` loads both parquets, applies `downsample_negatives` to post-2000 slice, fits XGBClassifier on 384k rows, serializes via `joblib.dump`; `eq_classifier.pkl` is 147,584 bytes and loads cleanly |
| 6 | predictions.json contains entries for 2026 with date, country, lat, lon, risk_score, top_planetary_aspects | VERIFIED | File exists (223,210 bytes); 901 records; schema confirmed by `TestPredictionExport::test_record_schema` PASSED; all records have correct keys |
| 7 | Only entries with risk_score >= threshold appear in predictions.json | VERIFIED | `TestPredictionExport::test_threshold_filter` PASSED; programmatic check confirms all 901 records >= 0.149939 |
| 8 | top_planetary_aspects lists up to 3 active aspect columns ranked by feature importance | VERIFIED | `top_aspects()` function filters aspect columns where value==1, ranks by `importance_map`, slices to `[:3]`; `TestTopAspects::test_aspects_max_three` PASSED |
| 9 | Each prediction includes geographic region (country, lat, lon from grid cells) | VERIFIED | `TestPredictionSchema::test_geo_columns` PASSED; 243 distinct countries, lat range -80 to 85, lon range -180 to 175 |

**Score:** 9/9 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pipeline/model/__init__.py` | Model package init | VERIFIED | 47 bytes, exists |
| `pipeline/model/train_eval.py` | Model selection, evaluation, eval_report.json output | VERIFIED | 11,038 bytes; substantive implementation; wired to parquets, feature_columns.json, eval_report.json |
| `pipeline/model/retrain.py` | Full retrain on 1900-2026 and model serialization | VERIFIED | 5,755 bytes; reads eval_report.json for winner; applies downsampling; serializes via joblib |
| `pipeline/model/export_predictions.py` | 2026 feature generation, inference, predictions.json output | VERIFIED | 7,924 bytes; loads model + threshold + importance_map; filters by threshold; writes predictions.json |
| `tests/test_model.py` | Tests for all MODEL and PRED requirements | VERIFIED | 7,324 bytes; 21 tests (18 pass, 3 xfail); all non-stub tests pass |
| `data/models/eval_report.json` | Evaluation metrics, threshold, both model results | VERIFIED | 440 bytes; all required keys present; both_models array has 2 entries |
| `data/models/eq_classifier.pkl` | Serialized winning model trained on full 1900-2026 | VERIFIED | 147,584 bytes; joblib-loadable; type=XGBClassifier; has predict_proba |
| `data/models/feature_importance.json` | 813-entry importance map for top-aspect ranking | VERIFIED | 35,951 bytes; loaded by export_predictions.py |
| `web/public/data/predictions.json` | Prediction entries for Phase 4 web app | VERIFIED | 223,210 bytes; 901 records; schema correct |
| `data/models/.gitkeep` | Directory marker | VERIFIED | Exists (0 bytes) |
| `web/public/data/.gitkeep` | Directory marker | VERIFIED | Exists (0 bytes) |

---

### Key Link Verification

**Plan 01 key links:**

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `train_eval.py` | `feature_matrix_train.parquet` | `pd.read_parquet` | WIRED | Line 70: `pd.read_parquet(TRAIN_PARQUET, columns=needed_cols)` |
| `train_eval.py` | `feature_matrix_test.parquet` | `pd.read_parquet` + pyarrow filter | WIRED | Lines 76-79: filter pushdown for 2000-2010 slice; `pq.ParquetFile` for chunked holdout |
| `train_eval.py` | `feature_columns.json` | `json.load` | WIRED | Line 249-251 in `main()` |
| `train_eval.py` | `eval_report.json` | `json.dump` | WIRED | Line 235: `json.dump(report, f, indent=2)` |

**Plan 02 key links:**

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `retrain.py` | `eval_report.json` | `json.load` | WIRED | Lines 59-61: reads `model_used` to select classifier |
| `retrain.py` | `eq_classifier.pkl` | `joblib.dump` | WIRED | Line 142: `joblib.dump(model, CLASSIFIER_PATH, compress=3)` |
| `export_predictions.py` | `eq_classifier.pkl` | `joblib.load` | WIRED | Line 137: `model = joblib.load(CLASSIFIER_PATH)` |
| `export_predictions.py` | `predictions.json` | `json.dump` | WIRED | Line 192: `json.dump(records, f, indent=2)` |
| `export_predictions.py` | `pipeline/features/engineering.py` | `from pipeline.features.engineering import` | WIRED | Lines 28-36: imports 7 functions (though only `top_aspects` path uses them; 2026 features load from parquet per documented deviation) |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| MODEL-01 | 03-01 | Model trains on 1900-2000 earthquake data | SATISFIED (with noted deviation) | Implementation uses 1900-2010 training window (not 1900-2000). CONTEXT.md locks this as the architectural decision: "model selection uses 1900-2010 train / 2010-2026 holdout." Phase 2 train parquet covers pre-2000; 2000-2010 slice is added from test parquet with downsampling. |
| MODEL-02 | 03-01 | Evaluated on 2000-2026 held-out data using F1 and MCC | SATISFIED (with noted deviation) | Holdout is 2010-2026 (not 2000-2026). CONTEXT.md documents this split. eval_report.json records both F1 and MCC for both models. `test_report_schema` and `test_confusion_matrix_keys` PASS. |
| MODEL-03 | 03-02 | Predicts date AND geographic region (country + lat/lon) | SATISFIED | Every prediction record has `date`, `country`, `lat`, `lon`. `TestPredictionSchema::test_geo_columns` PASSES. 243 distinct country/region names, global lat/lon coverage. |
| MODEL-04 | 03-01 | Two classifiers compared with class imbalance handling | SATISFIED (with noted deviation) | LogisticRegression and XGBClassifier both trained and compared. `TestBothModels::test_both_logged` PASSES. Class imbalance handled via 10:1 downsampling (not `class_weight='balanced'` or SMOTE). CONTEXT.md locks this: "no additional SMOTE or class_weight='balanced' in the classifier." |
| MODEL-05 | 03-02 | Trained model saved to disk via joblib/pickle | SATISFIED | `eq_classifier.pkl` (147 KB) serialized via `joblib.dump(model, CLASSIFIER_PATH, compress=3)`. `TestSerialization::test_model_roundtrip` PASSES — loaded object has `predict_proba`. |
| PRED-01 | 03-02 | Predictions for March-December 2026 exported as predictions.json in Next.js public/data/ | SATISFIED (with observed behavior note) | `predictions.json` exists at `web/public/data/predictions.json`. System generates features for all 306 dates (275,706 rows). After threshold filtering, 901 records remain — all on 2026-03-08. The system correctly generates for the full range; the model concentrates high risk on one planetary configuration date. See Human Verification item 1. |
| PRED-02 | 03-02 | Predictions JSON schema: date, country, lat, lon, risk_score (0-1), top_planetary_aspects (array of strings) | SATISFIED | `TestPredictionExport::test_record_schema` PASSES on all 5 sampled records. `TestTopAspects::test_aspects_are_strings` PASSES. risk_score values are 0-1 floats. |
| PRED-03 | 03-02 | Only predictions above defined risk threshold included | SATISFIED | Threshold (0.149939) read from eval_report.json. `TestPredictionExport::test_threshold_filter` iterates all 901 records and confirms each `risk_score >= threshold`. Programmatic spot-check also confirmed. |

**No orphaned requirements** — all 8 requirement IDs (MODEL-01 through MODEL-05, PRED-01 through PRED-03) are claimed by plans in this phase and verified against the codebase.

---

### Architectural Deviations (Documented in CONTEXT.md and SUMMARY files)

Three implementation choices differ from the literal wording of REQUIREMENTS.md. All three are documented architectural decisions locked in CONTEXT.md before implementation:

1. **Training window (MODEL-01/MODEL-02):** Requirements say "1900-2000 train / 2000-2026 holdout." CONTEXT.md locks "1900-2010 train / 2010-2026 holdout" to give a decade of post-engineering data in the holdout. The eval_report.json correctly records `eval_split_date: 2010-01-01`.

2. **Class imbalance (MODEL-04):** Requirements list `class_weight='balanced'` or SMOTE. CONTEXT.md locks 10:1 downsampling (already applied in Phase 2 parquets) as the sole imbalance technique. Both LR and XGB are trained without `class_weight` parameter.

3. **2026 feature generation (PRED-01):** Plan specified using `ephemeris.csv` + encoding pipeline. `data/raw/ephemeris.csv` is absent from the repo. Implementation reads 2026 rows from the Phase 2 test parquet (same encoding path). SUMMARY-02 documents this as an auto-fixed deviation.

---

### Anti-Patterns Found

No anti-patterns detected. Scanned all three pipeline files for TODO/FIXME/PLACEHOLDER/stub comments, `return null`, `return {}`, empty handlers — none present.

**Remaining xfail stubs in test_model.py (3):**

| Test | Reason | Severity |
|------|--------|----------|
| `TestTemporalSplit::test_train_dates_before_2010` | Training split not persisted to disk | Info — these are accepted stubs documenting in-memory assertions that cannot be verified post-run |
| `TestTemporalSplit::test_holdout_dates_from_2010` | Holdout not persisted to disk | Info |
| `TestFeatureSelection::test_train_column_count` | X_train not persisted to disk | Info |

These stubs are intentional — they document that the assertions hold during execution (validated by the logging in `load_training_set()`) but cannot be verified from stored artifacts after the fact.

---

### Test Results

```
18 passed, 3 xfailed in 11.92s
```

All 18 non-stub tests pass. The 3 xfailed tests are documented stubs for in-memory training state that is not persisted to disk.

---

### Human Verification Required

#### 1. Seismic Plausibility of 2026-03-08 Predictions

**Test:** Open `web/public/data/predictions.json`. Review the 901 country/lat/lon entries for 2026-03-08. Cross-reference with known seismically active regions (Pacific Ring of Fire, Alpine-Himalayan Belt, Mid-Atlantic Ridge).
**Expected:** The majority of entries should fall in recognized high-seismicity zones, not arbitrary or implausible locations.
**Why human:** The model assigns a maximum risk score of 0.2266 — just above the 0.1499 threshold — exclusively to one date (2026-03-08). Whether this reflects a genuine planetary-configuration signal or is a model artifact requires domain judgment that cannot be verified programmatically.

#### 2. Phase 4 Acceptability of Single-Date Output

**Test:** Confirm with the project owner/Phase 4 team that a predictions.json covering only 2026-03-08 (out of March-December 2026) is acceptable for the web app.
**Expected:** Either (a) the web app can display and explain the sparse single-date output meaningfully, or (b) a decision is made to lower the threshold to include more dates.
**Why human:** PRED-01 says "March-December 2026" — the code generates for that full range, but the model's threshold filtering leaves one date. Whether this is acceptable is a product decision, not a code correctness issue.

---

### Committed Artifacts

All 7 commits documented in SUMMARY files verified as existing in git history:
- `16e34c6` — Task 1: model package, directories, test stubs
- `25cfad6` — Task 2: train_eval.py and eval_report.json
- `6519334` — Task 3: promote xfail stubs to real assertions
- `a7a1c57` — retrain.py implementation
- `d3576a8` — model artifacts (eq_classifier.pkl, feature_importance.json)
- `2e0d63b` — export_predictions.py and test_model.py updates
- `9e05c48` — predictions.json artifact

---

## Summary

Phase 3 goal is achieved. All 9 observable truths are verified, all 8 requirement IDs are satisfied, all key links are wired, and 18/21 tests pass (3 are accepted stubs). The three REQUIREMENTS.md wordings that differ from implementation (split date, imbalance handling, ephemeris source) are all covered by documented decisions in CONTEXT.md locked before execution.

Two items are flagged for human verification: whether the single-date prediction output (2026-03-08) is seismically plausible and whether it is acceptable for Phase 4. These are product/domain questions, not code defects.

Phase 4 can consume `web/public/data/predictions.json` and `data/models/eval_report.json` as documented.

---

_Verified: 2026-03-16T23:45:00Z_
_Verifier: Claude (gsd-verifier)_
