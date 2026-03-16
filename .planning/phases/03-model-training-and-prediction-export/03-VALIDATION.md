---
phase: 3
slug: model-training-and-prediction-export
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ |
| **Config file** | none — uses pyproject.toml dev-dependencies |
| **Quick run command** | `uv run pytest tests/test_model.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_model.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 0 | MODEL-01 | unit | `uv run pytest tests/test_model.py::TestTemporalSplit::test_train_dates_before_2010 -x` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 0 | MODEL-01 | unit | `uv run pytest tests/test_model.py::TestFeatureSelection::test_train_column_count -x` | ❌ W0 | ⬜ pending |
| 3-01-03 | 01 | 0 | MODEL-02 | unit | `uv run pytest tests/test_model.py::TestEvalReport::test_report_schema -x` | ❌ W0 | ⬜ pending |
| 3-01-04 | 01 | 0 | MODEL-02 | unit | `uv run pytest tests/test_model.py::TestMetrics::test_mcc_known_values -x` | ❌ W0 | ⬜ pending |
| 3-01-05 | 01 | 0 | MODEL-03 | unit | `uv run pytest tests/test_model.py::TestPredictionSchema::test_geo_columns -x` | ❌ W0 | ⬜ pending |
| 3-01-06 | 01 | 0 | MODEL-04 | unit | `uv run pytest tests/test_model.py::TestBothModels::test_both_logged -x` | ❌ W0 | ⬜ pending |
| 3-01-07 | 01 | 0 | MODEL-05 | unit | `uv run pytest tests/test_model.py::TestSerialization::test_model_roundtrip -x` | ❌ W0 | ⬜ pending |
| 3-01-08 | 01 | 0 | PRED-01 | unit | `uv run pytest tests/test_model.py::TestPredictionExport::test_output_path -x` | ❌ W0 | ⬜ pending |
| 3-01-09 | 01 | 0 | PRED-02 | unit | `uv run pytest tests/test_model.py::TestPredictionExport::test_record_schema -x` | ❌ W0 | ⬜ pending |
| 3-01-10 | 01 | 0 | PRED-03 | unit | `uv run pytest tests/test_model.py::TestPredictionExport::test_threshold_filter -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_model.py` — stubs for MODEL-01 through MODEL-05, PRED-01 through PRED-03
- [ ] `pipeline/model/__init__.py` — module init for the new model subpackage
- [ ] `data/models/` directory — must exist before training scripts write artifacts
- [ ] `web/public/data/` directory — must exist before prediction export writes predictions.json
- [ ] Artifact smoke test: read both parquets, assert row counts > 10,000 and column count == 814 (813 features + EQIndicator) before any training begins

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| eval_report.json model rationale is legible | MODEL-04 | Free-text rationale field cannot be machine-verified | Open `data/models/eval_report.json`, confirm `model_used` key exists and the `both_models` array contains entries for both `LogisticRegression` and `XGBClassifier` with non-zero f1/mcc values |
| predictions.json file size is reasonable | PRED-01 | File size threshold is a judgment call | Run `wc -c web/public/data/predictions.json` — warn if > 2MB; check record count is < 5,000 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
