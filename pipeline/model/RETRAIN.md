# retrain.py: Final Model Training for Production

## Purpose

`retrain.py` is the **final model training and serialization pipeline**. It answers the question:

> **"Given that XGBoost won the model selection, how do we train the final production model using ALL available data?"**

This script:
1. **Loads the winning model** from `eval_report.json` (result of `train_eval.py`)
2. **Combines ALL data** (1900–2026) with consistent downsampling
3. **Trains the winning model** on the full dataset
4. **Extracts feature importance** for interpretability
5. **Serializes the model** to disk for use in predictions

---

## Why Retrain?

After model selection in `train_eval.py`, we want to use **all available data** for the final model. This is best-practice in ML:

```
Model Selection Phase:
  Train: 1900-2010 (1900-1999 + downsampled 2000-2010)
  Eval:  2010-2026
  Decision: XGBoost wins

Production Phase:
  Train: 1900-2026 (1900-1999 + ALL of 2000-2026, with 10:1 downsampling)
  Result: Model that has seen all historical data
```

**Rationale:** Once we've committed to XGBoost, there's no reason to withhold 2010-2026 data. Including it improves model performance (more training examples).

---

## High-Level Workflow

```
EVAL REPORT (from train_eval.py)
  └─ data/models/eval_report.json
     {
       "model_used": "XGBClassifier",
       "threshold": 0.150,
       ...
     }

        ↓

FEATURE MATRICES (same as train_eval.py)
  ├─ data/processed/feature_matrix_train.parquet (pre-2000, downsampled)
  └─ data/processed/feature_matrix_test.parquet (post-2000, all events)

        ↓

STEP 1: Load eval_report.json
  └─ Determine winning model (XGBClassifier)

        ↓

STEP 2: Load Feature Columns
  └─ 813-column feature list from feature_columns.json

        ↓

STEP 3: Load Data & Downsample
  ├─ Pre-2000 from train parquet (already 10:1 downsampled, ~160K rows)
  ├─ Post-2000 from test parquet (all events, ~8.3M rows)
  ├─ Apply 10:1 downsampling to post-2000 (~150K rows)
  └─ Combine: ~310K rows × 813 features

        ↓

STEP 4: Instantiate Winning Model
  └─ XGBClassifier with same hyperparameters as train_eval.py

        ↓

STEP 5: Train on Full Dataset
  ├─ Fit model to all 310K rows
  └─ Takes ~1-2 minutes

        ↓

STEP 6: Extract Feature Importance
  ├─ Get feature_importances_ from XGBoost
  ├─ Map to feature names
  └─ Save to data/models/feature_importance.json

        ↓

STEP 7: Serialize Model
  ├─ Use joblib.dump() with compression
  └─ Output: data/models/eq_classifier.pkl (~50 MB)

        ↓

USE TRAINED MODEL
  (Next: export_predictions.py loads this model for 2026 predictions)
```

---

## Detailed Steps

### STEP 1: Load eval_report.json

**File:** `main()`

```python
with open('data/models/eval_report.json') as f:
    report = json.load(f)

model_name = report['model_used']  # "XGBClassifier"
threshold = report['threshold']    # 0.150
mcc = report['mcc']               # 0.0014
```

**Why?** Determines which model architecture to instantiate and use for training.

**Typical Output:**
```json
{
  "model_used": "XGBClassifier",
  "f1_score": 0.0028,
  "mcc": 0.0014,
  "threshold": 0.15,
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

---

### STEP 2: Load Feature Columns

**File:** `main()`

```python
with open('data/processed/feature_columns.json') as f:
    feature_cols = json.load(f)

assert len(feature_cols) == 813
```

**Purpose:** Define which columns to extract from parquets and in what order.

Example first 5 columns:
```json
[
  "sun_lon_sin",
  "sun_lon_cos",
  "sun_sign_num_sin",
  "sun_sign_num_cos",
  "sun_nakshatra_num_sin",
  ...
]
```

---

### STEP 3: Load Data & Downsample

**File:** `main()`

#### Load Pre-2000 (already downsampled)

```python
pre2000 = pd.read_parquet('data/processed/feature_matrix_train.parquet')
# Size: ~160K rows (from original ~33M after 10:1 downsampling in Phase 2)
# Already balanced: positive + 10× sampled negatives
# Date range: 1900-01-01 to 1999-12-31
```

#### Load Post-2000 (not downsampled)

```python
post2000 = pd.read_parquet('data/processed/feature_matrix_test.parquet')
# Size before downsampling: ~8.3M rows
# Imbalanced: ~0.01% positive, ~99.99% negative
# Date range: 2000-01-01 to 2026-12-31
```

#### Apply 10:1 Downsampling to Post-2000

```python
post2000_ds = downsample_negatives(post2000, ratio=10, random_state=42)
# Keep: all EQIndicator=1 rows (~83K)
# Sample: 10× that many EQIndicator=0 rows (~830K) → ~83K after sampling
# Size after downsampling: ~166K rows
```

**Why 10:1?** Same ratio as training in `train_eval.py` for consistency. Balances:
- **Too high ratio (1:1):** Throws away 99% of negative examples; wastes data
- **Too low ratio (100:1):** Keeps extreme imbalance; model may ignore negatives
- **10:1:** Proven effective in practice; improves convergence without losing information

#### Combine Pre & Post

```python
final_train = pd.concat([pre2000, post2000_ds])
# Final size: ~160K + ~166K = ~326K rows
# Dtype: float32 (~813 GB total at float32)
# Balanced: ~10:1 positive:negative throughout
```

---

### STEP 4: Instantiate Winning Model

**File:** `main()`

**Case: XGBClassifier (current winner)**

```python
if model_name == "XGBClassifier":
    model = XGBClassifier(
        n_estimators=100,      # 100 boosting rounds (same as train_eval.py)
        max_depth=6,           # Tree depth
        random_state=42,       # Reproducibility
        eval_metric='logloss'  # Binary crossentropy
    )
```

**Case: LogisticRegression (if it had won)**

```python
elif model_name == "LogisticRegression":
    model = LogisticRegression(
        C=1,                   # Regularization strength
        penalty='l1',          # L1 penalty
        solver='liblinear',    # Only solver supporting L1
        max_iter=1000,         # Iterations
        random_state=42
    )
```

**Key Point:** Hyperparameters are **identical** to `train_eval.py`. This ensures consistency.

---

### STEP 5: Train on Full Dataset

**File:** `main()`

```python
X = final_train[feature_cols].to_numpy(dtype='float32')
y = final_train['EQIndicator'].to_numpy()

logger.info("Fitting %s on full 1900-2026 dataset ...", model_name)
model.fit(X, y)
logger.info("Training complete")
```

**Timing:**
- XGBoost (100 trees): ~1-2 minutes
- LogisticRegression: ~10 seconds

**Memory:**
- X_train: ~1 GB (326K rows × 813 float32)
- Model in-memory: ~50 MB
- **Peak RAM: ~1.5 GB**

**Output:** Fitted `model` object with learned parameters

---

### STEP 6: Extract Feature Importance

**File:** `main()`

```python
if model_name == "LogisticRegression":
    # Linear model: absolute value of coefficients = importance
    importances = np.abs(model.coef_[0])
else:  # XGBClassifier
    # Tree-based: built-in feature_importances_ (gain-based)
    importances = model.feature_importances_

# Map to feature names
importance_map = dict(zip(feature_cols, importances.tolist()))

# Save to JSON
with open('data/models/feature_importance.json', 'w') as f:
    json.dump(importance_map, f)
```

**What is Feature Importance?**

| Model | Importance Metric | Interpretation |
|---|---|---|
| **LogisticRegression** | Abs(coefficient) | Magnitude of linear contribution; how much the feature shifts the log-odds |
| **XGBoost** | Gain-based | How much each feature reduces loss across all trees |

**Example Output:**
```json
{
  "sun_lon_sin": 0.0145,
  "sun_lon_cos": 0.0098,
  "moon_lon_sin": 0.0234,
  "moon_lon_cos": 0.0167,
  ...
  "tithi_sin": 0.0001,
  "tithi_cos": 0.0001,
  ...
}
```

**Top Features Insight:** Features with highest importance are the strongest predictors of earthquake risk in the model.

---

### STEP 7: Serialize Model

**File:** `main()`

```python
import joblib

joblib.dump(model, 'data/models/eq_classifier.pkl', compress=3)
size_kb = Path('data/models/eq_classifier.pkl').stat().st_size / 1024

logger.info("Model serialized to eq_classifier.pkl (%.0f KB)", size_kb)
```

**Format:** Pickle with gzip compression level 3 (balance speed vs compression ratio)

**Size:**
- Uncompressed: ~100 MB
- Compressed: ~50 MB

**Why Pickle?** 
- Standard Python serialization (joblib wrapper)
- Preserves all model state (coefficients, trees, hyperparameters)
- Used by scikit-learn, XGBoost communities

**Alternative Formats:**
- ONNX (cross-language compatibility)
- SavedModel (TensorFlow format)
- PMML (predictive model markup)

For this project, joblib/pickle is sufficient and fast.

---

## Input/Output Summary

### Inputs
| File | Purpose | Size |
|---|---|---|
| `data/models/eval_report.json` | Model selection result (which model won?) | 2 KB |
| `data/processed/feature_matrix_train.parquet` | Pre-2000 data (downsampled) | 3 GB |
| `data/processed/feature_matrix_test.parquet` | Post-2000 data (all events) | 35 GB |
| `data/processed/feature_columns.json` | Feature column order | 20 KB |

### Outputs
| File | Purpose | Size |
|---|---|---|
| `data/models/eq_classifier.pkl` | Trained model (serialized) | 50 MB |
| `data/models/feature_importance.json` | Feature importance map | 20 KB |

---

## Data Timeline

### Before Retrain

**Model Selection Phase (train_eval.py):**
```
Training:   1900-2010 (pre-2000 + downsampled 2000-2010) → ~300K rows
Evaluation: 2010-2026 (holdout) → 5.8M rows
Decision:   XGBoost wins (MCC 0.0014 > LogisticRegression 0.0012)
```

### After Retrain

**Production Phase (retrain.py):**
```
Training:   1900-2026 (pre-2000 + ALL 2000-2026, downsampled 10:1) → ~326K rows
Result:     Trained model with full historical data
Use:        For 2026 predictions (export_predictions.py)
```

**Why Include 2010-2026 in Retrain?**
- We know XGBoost wins, so no risk of overfitting to holdout
- More training data = better generalization
- Best-practice in ML: use all data once model is selected

---

## Key Differences from train_eval.py

| Aspect | train_eval.py | retrain.py |
|---|---|---|
| **Purpose** | Model selection | Final training |
| **Training Data** | 1900-2010 (~300K rows) | 1900-2026 (~326K rows) |
| **Models Trained** | 2 (LogisticRegression + XGBoost) | 1 (winner only) |
| **Holdout Evaluation** | Yes (2010-2026) | No |
| **Output** | eval_report.json | eq_classifier.pkl + feature_importance.json |
| **Use Case** | Decide which model to use | Serve predictions to users |

---

## Reproducibility

### Fixed Random Seeds
```python
random_state=42  # Both models
```
This ensures:
- Same downsampling (same negative examples selected each time)
- Same model initialization
- Identical results on re-run

### Deterministic Sorting
```python
downsample_negatives(..., random_state=42)
```
Uses numpy seeding for reproducible random sampling.

---

## Debugging & Validation

### Expected Output

```bash
$ uv run python -m pipeline.model.retrain

[logs...]
Retraining winner model: XGBClassifier
Loaded 813 feature columns
Reading train parquet (pre-2000, already downsampled): data/processed/feature_matrix_train.parquet
Pre-2000 partition: 160241 rows
Reading test parquet (post-2000, all dates): data/processed/feature_matrix_test.parquet
Post-2000 partition before downsampling: 8286978 rows (positive=82869, negative=8204109)
Post-2000 after downsampling: 166041 rows
Full retrain dataset: 326282 rows
Training arrays prepared: X=(326282, 813), y=(326282,)
Fitting XGBClassifier on full 1900-2026 dataset ...
Training complete
Feature importance written to data/models/feature_importance.json
Model serialized to data/models/eq_classifier.pkl (52 MB)
Retrain complete.
```

### Verify Outputs

```bash
# Check model exists and size
ls -lh data/models/eq_classifier.pkl
# Output: -rw-r--r-- 1 user group 52M eq_classifier.pkl

# Check feature importance
head data/models/feature_importance.json | jq '.[] | keys[0:5]'
# Output: Top 5 feature names

# Load and test model
python -c "
import joblib
model = joblib.load('data/models/eq_classifier.pkl')
print(f'Model type: {type(model).__name__}')
print(f'Number of estimators: {model.n_estimators}')
print(f'Feature importances shape: {model.feature_importances_.shape}')
"
```

### Common Issues

**Issue:** "No such file or directory: data/models/eval_report.json"
- **Cause:** `train_eval.py` not run yet
- **Fix:** Run `uv run python -m pipeline.model.train_eval` first

**Issue:** "Expected 813 features, got N"
- **Cause:** feature_columns.json mismatch
- **Fix:** Regenerate from `pipeline.features.engineering`

**Issue:** "KeyError: XGBClassifier"
- **Cause:** eval_report.json has different model_name spelling
- **Fix:** Check eval_report.json; ensure exact match with code

**Issue:** "MemoryError during training"
- **Cause:** Insufficient RAM for 326K × 813 float32 matrix
- **Fix:** Use alternative: stream training with partial fits, or downsample further

---

## Performance Characteristics

### Time
- Load parquets & downsampling: ~2 minutes
- XGBoost training: ~2 minutes
- Feature importance extraction: <1 second
- Serialization: ~5 seconds
- **Total: ~5 minutes**

### Memory
- Final training set (X, y): ~1 GB
- Model in-memory: ~50 MB
- **Peak RAM: ~1.5 GB**

### Disk
- Input: 38 GB (parquets)
- Output: 50 MB (model) + 20 KB (feature importance)
- **Net change: -37.95 GB**

---

## Integration with Pipeline

### Upstream: train_eval.py
```
Produces → data/models/eval_report.json
```

### Downstream: export_predictions.py
```
Consumes ← data/models/eq_classifier.pkl
           data/models/feature_importance.json
Produces → web/public/data/predictions.json
```

### Web App
```
Reads data/models/feature_importance.json
Displays top features on methodology page
```

---

## FAQ

**Q: Can I retrain with different hyperparameters?**

A: Yes, but you'll need to modify `eval_report.json` manually or re-run `train_eval.py` with new hyperparameters.

```python
# In retrain.py
model = XGBClassifier(
    n_estimators=200,     # Increased
    max_depth=8,          # Deeper trees
    learning_rate=0.05,   # New parameter
    random_state=42
)
```

Then rerun and generate new predictions.

**Q: Should I use the validation threshold (0.150) or the one from retrain?**

A: Use the **validation threshold from eval_report.json (0.150)**. This was selected to optimize F1 on held-out data.

If you retrain and re-compute threshold on the same training set, you'll overfit.

**Q: What if LogisticRegression had won?**

A: `retrain.py` handles both:
```python
if model_name == "LogisticRegression":
    # instantiate and train LogisticRegression
else:
    # instantiate and train XGBClassifier
```

Just run the same script; it auto-detects the winner.

**Q: Can I combine feature importance from both models?**

A: Yes, modify the script:
```python
importance_map_logreg = extract_importance(logreg)
importance_map_xgb = extract_importance(xgb)
importance_combined = {
    k: (importance_map_logreg.get(k, 0) + importance_map_xgb.get(k, 0)) / 2
    for k in importance_map_logreg.keys()
}
```

But for simplicity, use the winner's importance.

**Q: How do I update the model mid-year?**

A: If new earthquake data arrives (USGS updates):
1. Re-run `pipeline.data.usgs` to get new events
2. Re-run `pipeline.features.engineering` to rebuild matrices
3. Re-run `pipeline.model.train_eval` (optional; only needed if hyperparameters change)
4. Re-run `pipeline.model.retrain` to retrain on new data
5. Re-run `pipeline.model.export_predictions` to generate new 2026 predictions

The entire pipeline is designed to be re-runnable.

**Q: Is the serialized model portable across Python versions?**

A: Joblib pickle has good **backwards compatibility** but may break with:
- Different scikit-learn/XGBoost versions
- Different Python major versions (3.11 vs 3.12)

**Best practice:** Include requirements in pickle metadata or use ONNX for production.

---

## Related Files

- **Input:** [pipeline/model/train_eval.py](./train_eval.py) – Model selection
- **Input:** [data/models/eval_report.json](../../data/models/eval_report.json) – Evaluation results
- **Input:** [pipeline/features/engineering.py](../features/engineering.py) – Feature engineering
- **Output:** [data/models/eq_classifier.pkl](../../data/models/eq_classifier.pkl) – Trained model
- **Output:** [data/models/feature_importance.json](../../data/models/feature_importance.json) – Feature importance
- **Next:** [pipeline/model/export_predictions.py](./export_predictions.py) – Generate 2026 predictions
- **Docs:** [PIPELINE_TRANSFORMATION.md](../../PIPELINE_TRANSFORMATION.md) – Full pipeline overview
- **Docs:** [TRAIN_EVAL.md](./TRAIN_EVAL.md) – Model selection explanation
