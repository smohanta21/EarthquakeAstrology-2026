---
phase: 2
slug: feature-engineering
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-15
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0 (installed as dev dependency) |
| **Config file** | `pyproject.toml` (no `[tool.pytest]` section needed yet) |
| **Quick run command** | `pytest tests/test_engineering.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_engineering.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 0 | FEAT-01..05 | unit | `pytest tests/test_engineering.py -x -q` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02 | 1 | FEAT-05 | unit | `pytest tests/test_engineering.py::TestGridCells tests/test_engineering.py::TestCountryParsing -x` | ❌ W0 | ⬜ pending |
| 2-02-02 | 02 | 1 | FEAT-04 | unit | `pytest tests/test_engineering.py::TestEQIndicator tests/test_engineering.py::TestEQIndicatorCollapse -x` | ❌ W0 | ⬜ pending |
| 2-03-01 | 03 | 1 | FEAT-01 | unit | `pytest tests/test_engineering.py::TestColumnInventory tests/test_engineering.py::TestNoRawColumns -x` | ❌ W0 | ⬜ pending |
| 2-03-02 | 03 | 1 | FEAT-02 | unit | `pytest tests/test_engineering.py::TestCyclicalEncoding -x` | ❌ W0 | ⬜ pending |
| 2-04-01 | 04 | 2 | FEAT-03 | unit | `pytest tests/test_engineering.py::TestTemporalSplit tests/test_engineering.py::TestEncoderFitScope tests/test_engineering.py::TestDownsamplingScope -x` | ❌ W0 | ⬜ pending |
| 2-05-01 | 05 | 2 | FEAT-01..05 | integration | `pytest tests/test_engineering.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_engineering.py` — stubs for all Phase 2 test cases (FEAT-01 through FEAT-05)
- [ ] `pipeline/features/__init__.py` — make features a package
- [ ] `pipeline/features/engineering.py` — main module under test (stub)
- [ ] `data/processed/` directory — created by Wave 0 test setup or script
- [ ] `pyarrow` install: `uv add pyarrow` — required for `pd.to_parquet()` on test set

*Wave 0 must be completed before any Wave 1 tasks begin.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Feature matrix CSV opens correctly in pandas with expected dtypes | FEAT-01 | End-to-end file I/O check | `import pandas as pd; df = pd.read_parquet('data/processed/feature_matrix_train.parquet'); df.info()` |
| Temporal assertion passes on actual full dataset | FEAT-03 | Requires full pipeline run (~14M row cross-join) | Run `python pipeline/features/engineering.py` and verify exit code 0 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
