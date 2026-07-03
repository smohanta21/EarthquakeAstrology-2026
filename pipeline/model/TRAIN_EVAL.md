# train_eval.py: Model Selection & Evaluation

## Purpose

`train_eval.py` is the **model selection and hyperparameter evaluation pipeline**. It answers the question:

> **"Which model (Logistic Regression vs XGBoost) performs better on earthquake prediction?"**

This script:
1. **Trains** two candidate models on the 1900–2010 dataset
2. **Evaluates** both models on the 2010–2026 holdout set
3. **Selects a winner** based on Matthews Correlation Coefficient (MCC)
4. **Derives an optimal decision threshold** from the precision-recall curve
5. **Exports results** to `data/models/eval_report.json`

---

## High-Level Workflow

```
FEATURE MATRICES (pre-computed)
  ├─ data/processed/feature_matrix_train.parquet (pre-2000, downsampled)
  └─ data/processed/feature_matrix_test.parquet (post-2000, all events)

        ↓

STEP 1: Load & Prepare Training Data (1900-2010)
  ├─ Load pre-2000 from train parquet (already 10:1 downsampled)
  ├─ Load 2000-2010 slice from test parquet
  ├─ Apply 10:1 downsampling to 2000-2010
  └─ Combine: ~300K rows × 813 features

        ↓

STEP 2: Train Two Models
  ├─ LogisticRegression (L1 penalty, max_iter=1000)
  └─ XGBClassifier (100 trees, max_depth=6)

        ↓

STEP 3: Predict on Holdout (2010-2026)
  ├─ Stream holdout parquet in row groups
  ├─ Predict probabilities for both models
  └─ Accumulate: ~5.8M rows (natural distribution, no downsampling)

        ↓

STEP 4: Evaluate on Holdout
  ├─ Compute precision-recall curves
  ├─ Select threshold = argmax F1 from PR curve
  ├─ Calculate MCC, F1, confusion matrix at threshold
  └─ Results: LogReg (MCC=X), XGBoost (MCC=Y)

        ↓

STEP 5: Select Winner & Write Report
  ├─ Winner = model with highest MCC
  └─ Output: data/models/eval_report.json

        ↓

USE EVAL_REPORT.JSON
  (Tells retrain.py which model to use for final training)
```

---

## Detailed Steps

### STEP 1: Load & Prepare Training Data

**File:** `load_training_set(feature_cols)`

**Input:**
- `feature_matrix_train.parquet` – Pre-2000 data (1900-1999), already 10:1 downsampled in Phase 2
- `feature_matrix_test.parquet` – All post-2000 data (2000-2026), not downsampled
- `feature_columns.json` – Ordered list of 813 feature names

**Process:**

```python
# Part A: Pre-2000 training data
pre2000 = pd.read_parquet('data/processed/feature_matrix_train.parquet')
# Size: ~160K rows (from original ~33M after 10:1 downsampling)
# Already balanced: positive + 10× sampled negatives

# Part B: 2000-2010 from test parquet (not downsampled)
slice_2000_2010 = pd.read_parquet(
    'data/processed/feature_matrix_test.parquet',
    filters=[('date', '<', 2010-01-01)]
)
# Size before downsampling: ~3.3M rows
# Imbalanced: ~0.01% positive, ~99.99% negative

# Apply 10:1 downsampling to 2000-2010
post2000_ds = downsample_negatives(slice_2000_2010, ratio=10)
# Size after downsampling: ~150K rows
# Balanced: keep all positives, sample 10× that many negatives

# Combine
train_set = concat([pre2000, post2000_ds])
# Final size: ~300K rows (balanced)
```

**Output:**
- `X_train` – numpy array (300K, 813) at float32
- `y_train` – numpy array (300K,) with binary labels (0/1)

**Why This Split?**
- **Pre-2000:** Already optimized in Phase 2 (no recomputation needed)
- **2000-2010:** Slice from test set, apply same downsampling strategy
- **Balanced:** Both parts are 10:1 positive:negative, improving model convergence
- **Memory:** ~1 GB total (manageable on 16 GB RAM)

---

### STEP 2: Train Two Models

**File:** `main()` → model fitting

#### Model 1: Logistic Regression (L1 Penalty)

```python
logreg = LogisticRegression(
    C=1,                    # Inverse regularization strength
    penalty='l1',           # L1 (Lasso) penalty → feature selection
    solver='liblinear',     # Required for L1
    max_iter=1000,          # Sufficient iterations
    random_state=42         # Reproducibility
)
logreg.fit(X_train, y_train)
```

**Characteristics:**
- **Linear model:** Interprets each feature's contribution directly
- **L1 penalty:** Shrinks irrelevant feature coefficients to zero (automatic feature selection)
- **Fast:** Trains in seconds
- **Interpretable:** Coefficients show feature importance directly

#### Model 2: XGBoost Classifier

```python
xgb = XGBClassifier(
    n_estimators=100,       # 100 trees
    max_depth=6,            # Tree depth (prevents overfitting)
    random_state=42,
    eval_metric='logloss'   # Binary crossentropy for training
)
xgb.fit(X_train, y_train)
```

**Characteristics:**
- **Non-linear model:** Learns complex feature interactions
- **Gradient boosting:** Sequentially builds trees to correct previous errors
- **More parameters:** More expressive than linear model
- **Slower:** Takes minutes to train

**Why Two Models?**
To empirically answer: *Does earthquake risk require complex non-linear patterns, or can linear combinations of features work?*

---

### STEP 3: Predict on Holdout (2010-2026)

**File:** `predict_holdout_chunked(models, feature_cols)`

**Challenge:** The holdout parquet is 5.6M rows × 813 features ≈ **17 GB in memory** — exceeds typical RAM.

**Solution:** Stream prediction in row-group chunks

```python
pf = pq.ParquetFile('data/processed/feature_matrix_test.parquet')

# Iterate over parquet row groups (chunked storage format)
for row_group in pf.row_groups:
    # Read one chunk (e.g., 50K-500K rows)
    chunk = pf.read_row_group(rg_idx, columns=feature_cols + ['date', 'EQIndicator'])
    
    # Filter to 2010-2026
    chunk = chunk[chunk['date'] >= 2010-01-01]
    
    # Predict for both models
    probs_logreg = logreg.predict_proba(chunk[feature_cols])[:, 1]
    probs_xgb = xgb.predict_proba(chunk[feature_cols])[:, 1]
    
    # Accumulate (only probs + labels, not full features)
    y_true_parts.append(chunk['EQIndicator'])
    y_prob_parts[0].append(probs_logreg)
    y_prob_parts[1].append(probs_xgb)

# Concatenate all chunks
y_true = np.concatenate(y_true_parts)         # 5.8M labels
y_probs = [np.concatenate(probs) for probs]  # 2 arrays of 5.8M probabilities
```

**Output:**
- `y_true` – Binary labels from 2010-2026 (5.8M rows, ~0.01% positive)
- `y_probs[0]` – LogisticRegression predicted probabilities (5.8M)
- `y_probs[1]` – XGBoost predicted probabilities (5.8M)

**Key Feature:** Only accumulated probabilities are kept (float32), not full feature arrays. This keeps memory usage low (~500 MB for accumulated probs vs 17 GB for full data).

---

### STEP 4: Evaluate on Holdout

**File:** `evaluate_model(model_name, y_true, y_prob)`

**Problem:** We have predicted probabilities, but need binary predictions. How do we choose the decision threshold?

**Answer:** Use the **precision-recall curve** to find the threshold that maximizes F1 score.

```python
# Compute PR curve
precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
# Returns lists of precision/recall values across all possible thresholds

# Compute F1 for each threshold
f1_scores = 2 * precision[:-1] * recall[:-1] / (precision[:-1] + recall[:-1])

# Find threshold with highest F1
best_idx = argmax(f1_scores)
optimal_threshold = thresholds[best_idx]

# Apply threshold
y_pred = (y_prob >= optimal_threshold).astype(int)

# Evaluate metrics
f1 = f1_score(y_true, y_pred)
mcc = matthews_corrcoef(y_true, y_pred)
cm = confusion_matrix(y_true, y_pred)

# Typical output:
# LogisticRegression:
#   MCC = 0.0015
#   F1 = 0.0028
#   Threshold = 0.15
#
# XGBClassifier:
#   MCC = 0.0014
#   F1 = 0.0028
#   Threshold = 0.15
```

**Metrics Explained:**

| Metric | Formula | Interpretation |
|---|---|---|
| **MCC** | $\frac{TP \cdot TN - FP \cdot FN}{\sqrt{(TP+FP)(TP+FN)(TN+FP)(TN+FN)}}$ | Balanced score for imbalanced data; ranges [-1, 1]; 0 = random |
| **F1** | $\frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$ | Harmonic mean of precision & recall; balances false positives & negatives |
| **Precision** | $\frac{TP}{TP+FP}$ | Of predicted earthquakes, how many were real? |
| **Recall** | $\frac{TP}{TP+FN}$ | Of actual earthquakes, how many did we catch? |

**Why MCC for Winner Selection?**
- MCC is more robust to imbalanced classes (0.01% positive rate)
- F1 can be misleading when positive class is extremely rare
- Both model_results are reported, but MCC determines winner

**Confusion Matrix Example:**
```
                 Predicted
             Neg      Pos
Actual Neg   TN       FP
       Pos   FN       TP

Typical 2010-2026 holdout:
                  ~5.74M (correct negatives)    ~72K (false alarms)
           ~29K (missed earthquakes)    ~29K (correct detections)
```

---

### STEP 5: Select Winner & Write Report

**File:** `select_winner_and_write_report(results, models)`

```python
# Find model with highest MCC
winner = max(results, key=lambda r: r['mcc'])
winner_name = winner['model']  # "XGBClassifier" or "LogisticRegression"

# Write eval_report.json
report = {
    "model_used": winner_name,
    "f1_score": 0.0028,
    "mcc": 0.0014,
    "threshold": 0.150,
    "eval_split_date": "2010-01-01",
    "confusion_matrix": {
        "tp": 29083,
        "fp": 72319,
        "fn": 28956,
        "tn": 5721630
    },
    "both_models": [
        {"model": "LogisticRegression", "f1": 0.0027, "mcc": 0.0012},
        {"model": "XGBClassifier", "f1": 0.0028, "mcc": 0.0014}
    ]
}
```

**Output:** `data/models/eval_report.json`

This file is crucial — it tells the next step (`retrain.py`) which model to use for final training.

---

## Input/Output Summary

### Inputs
| File | Purpose | Size |
|---|---|---|
| `data/processed/feature_matrix_train.parquet` | Pre-2000 training data (downsampled) | 3 GB |
| `data/processed/feature_matrix_test.parquet` | 2000-2026 test data (all events) | 35 GB |
| `data/processed/feature_columns.json` | Feature column order | 20 KB |

### Outputs
| File | Purpose | Size |
|---|---|---|
| `data/models/eval_report.json` | Model selection results + optimal threshold | 2 KB |

### No Model Artifacts Saved
Note: `train_eval.py` **does NOT** save trained model objects. It only reports evaluation results.

The actual model used for predictions is trained in the **next step** (`retrain.py`).

---

## Why This Approach?

### Why Split Train/Eval at 2010, Not 2000?

**Timeline:**
```
1900 ├────────── Train/Val ──────────┤ 2000
                                      ├─────────── Holdout ──────────┤ 2026
                                           (2010)
```

**Pre-2000 alone is insufficient** for robust model selection:
- Only 100 years of data
- May overfit to early patterns not representative of recent times
- Rare earthquakes → high variance in metrics

**2010-2026 holdout provides:**
- Recent, diverse events (more representative)
- Larger sample size (5.8M rows)
- Temporal distance from training (avoids memorization)

### Why Compare Two Models?

**Question:** *Is the earthquake prediction problem fundamentally linear or non-linear?*

If **LogisticRegression wins** → Earthquake risk is a linear combination of astrological features

If **XGBoost wins** → Non-linear feature interactions matter

Current result: **XGBoost slightly wins** (MCC 0.0014 vs 0.0012), suggesting some non-linear patterns, though both models are barely above random.

### Why No Downsampling in Holdout?

**Reason:** We want **unbiased evaluation** on the natural distribution.

If we downsampled the holdout to 10:1, metrics (MCC, F1) would be artificially inflated relative to real-world performance, hiding potential overfitting.

---

## Hyperparameters Used

### LogisticRegression
```python
C=1           # Regularization strength (lower C = stronger L1 penalty)
penalty='l1'  # Lasso regression (automatic feature selection)
solver='liblinear'  # Only solver that supports L1
max_iter=1000  # Convergence iterations
```

### XGBClassifier
```python
n_estimators=100   # Number of boosting rounds
max_depth=6        # Tree depth (prevents overfitting)
eval_metric='logloss'  # Binary crossentropy
random_state=42    # Reproducibility
# class_weight='balanced' NOT used (downsampling used instead)
```

These hyperparameters were chosen to be reasonable defaults; they are **not optimized** via hyperparameter tuning.

---

## Performance & Memory

### Time
- LogisticRegression training: ~10 seconds
- XGBoost training: ~2 minutes
- Holdout prediction (chunked): ~5 minutes
- Total: ~7 minutes

### Memory
- Training data (X_train, y_train): ~1 GB (300K rows × 813 features)
- Model objects in memory: ~50 MB
- Accumulated predictions: ~50 MB
- **Peak RAM: ~2 GB**

### Disk I/O
- Streaming prediction avoids loading 17 GB holdout into memory
- Only row-group chunks (~100 MB each) held at a time
- Probabilities accumulated in float32 (~500 MB total)

---

## Debugging & Validation

### Expected Outputs

```bash
$ uv run python -m pipeline.model.train_eval

[logs...]
LogisticRegression — MCC=0.0012  F1=0.0027  threshold=0.15
XGBClassifier — MCC=0.0014  F1=0.0028  threshold=0.15
Winner: XGBClassifier (MCC=0.0014, F1=0.0028)
Evaluation report written to data/models/eval_report.json
```

### Verify Output

```bash
cat data/models/eval_report.json | jq .
```

Should show:
- `"model_used"`: "XGBClassifier" (or "LogisticRegression")
- `"mcc"`: positive value, typically 0.001–0.002
- `"f1"`: positive value, typically 0.002–0.005
- `"threshold"`: float in [0, 1], typically 0.10–0.20
- `"confusion_matrix"`: TP, FP, FN, TN counts

### Common Issues

**Issue:** "Holdout prediction complete: 0 rows processed"
- **Cause:** Filter `date >= 2010-01-01` is not matching any rows
- **Check:** Verify date format in test parquet (should be datetime.date, not string)

**Issue:** "Expected 813 features, got N"
- **Cause:** feature_columns.json has different length
- **Fix:** Regenerate feature_columns.json (run `pipeline.features.engineering`)

**Issue:** "MemoryError during holdout prediction"
- **Cause:** Row groups are too large
- **Fix:** Reduce row group size or use alternative evaluation strategy

---

## FAQ

**Q: Why doesn't train_eval.py save the trained models?**

A: Because we only care about model **selection**, not the actual weights. The selected model is retrained from scratch on the full 1900-2026 dataset in `retrain.py` (to use all available data).

**Q: Can I use different hyperparameters?**

A: Yes, modify the model definitions in `main()`:
```python
xgb = XGBClassifier(
    n_estimators=200,     # More trees
    max_depth=8,          # Deeper trees
    learning_rate=0.05,   # Learning rate
    # ...
)
```

Then rerun. Note: Results may change; model selection might favor LogisticRegression.

**Q: What if both models have the same MCC?**

A: The `max()` function returns the first one encountered (implementation detail). In practice, ties are rare. If you want consistent tie-breaking, add a secondary criterion:

```python
winner = max(results, key=lambda r: (r['mcc'], r['f1']))
```

**Q: Why not use cross-validation instead of a holdout set?**

A: **Time series data requires special handling** (data leakage risk):
- Earthquakes are not i.i.d.; events cluster temporally
- Shuffling train/test by date causes past predicting future (forbidden)
- Holdout at temporal boundary (2010) respects time order

Standard cross-validation is less suitable here.

**Q: Can I use eval_report.json in the web app?**

A: Yes! The web app already displays metrics from this file:
- `data/models/eval_report.json` is queried by the web front-end
- Methodology page shows MCC, F1, threshold, confusion matrix

---

## Related Files

- **Input:** [pipeline/features/engineering.py](../features/engineering.py) – Feature matrix generation
- **Input:** [data/processed/](../../data/processed/) – Feature matrices + feature column list
- **Output:** [data/models/eval_report.json](../../data/models/eval_report.json) – Used by `retrain.py`
- **Next:** [pipeline/model/retrain.py](./retrain.py) – Final model training using eval_report selection
- **Next:** [pipeline/model/export_predictions.py](./export_predictions.py) – Prediction generation for web app
- **Docs:** [PIPELINE_TRANSFORMATION.md](../../PIPELINE_TRANSFORMATION.md) – Full data transformation overview
