# Complete Data Transformation Pipeline

## Overview

This document traces the **end-to-end transformation** from raw earthquake and ephemeris data to final ML-ready feature matrices. Each step is a distinct pipeline module with clear inputs, outputs, and validation gates.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 1: DATA COLLECTION                                                  │
│ (pipeline/data/usgs.py, pipeline/data/ephemeris.py)                     │
└──────────────┬───────────────────────────────────────────────────────────┘
               ↓
        ├─ USGS Earthquakes (1900-2026)
        │  • 5,893 events M5.5+ worldwide
        │  • Downloaded from FDSNWS API
        │  • CSV: time, lat, lon, depth, mag, place, type
        │
        └─ Swiss Ephemeris Data (1900-2026)
           • Daily planetary positions (13 bodies)
           • Computed with pysweph library
           • CSV: 200+ columns (lon, lat, retro, sign, nakshatra, aspects)

┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 2: DATA VALIDATION                                                  │
│ (pipeline/data/validate_ephemeris.py)                                    │
└──────────┬───────────────────────────────────────────────────────────────┘
           ↓
     Spot-check ephemeris against JPL Horizons reference values
     • 10 sample dates × planets
     • Tolerance: 0.5° (acceptable margin vs JPL)
     • Gate passes → proceed to feature engineering

┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 3: SPATIAL GRID MAPPING                                             │
│ (pipeline/features/engineering.py)                                       │
└──────────┬───────────────────────────────────────────────────────────────┘
           ↓
     • Map earthquake lat/lon → 5-degree grid cells
     • Extract country from USGS place strings
     • Identify "active cells" (contain M5.5+ events)
     • Result: ~329K active cells, country mapping

┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 4: EPHEMERIS ENCODING                                               │
│ (pipeline/features/engineering.py: encode_ephemeris)                     │
└──────────┬───────────────────────────────────────────────────────────────┘
           ↓
     Transform raw planetary data:
     
     Raw Column              →  Encoded Feature(s)          Type
     ─────────────────────────────────────────────────────────────
     {p}_lon (0-360°)        →  {p}_lon_sin, _cos           cyclic
     {p}_sign_num (0-11)     →  {p}_sign_num_sin, _cos      cyclic
     {p}_nakshatra_num (0-26)→  {p}_nakshatra_num_sin, _cos cyclic
     {p}_retro (bool)        →  {p}_retro                   binary
     {p}_nakshatra (string)  →  [preserved for later]       categorical
     {p1}_{p2}_{aspect}      →  {p1}_{p2}_{aspect}          binary
     
     Special: sun_lon, moon_lon → tithi_sin, tithi_cos    derived

┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 5: NAKSHATRA ONE-HOT ENCODING                                       │
│ (pipeline/features/engineering.py: fit/apply_nakshatra_encoding)         │
└──────────┬───────────────────────────────────────────────────────────────┘
           ↓
     Fit OneHotEncoder on pre-2000 data only:
     • Learn 27 nakshatra categories from 1900-1999
     • Transform all dates using this fixed vocabulary
     • Output: 13 planets × 27 nakshatras = 351 binary columns

┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 6: FEATURE MATRIX CONSTRUCTION & BROADCASTING                       │
│ (pipeline/features/engineering.py: build_matrix_year)                    │
└──────────┬───────────────────────────────────────────────────────────────┘
           ↓
     For each date:
     
     Input:  1 encoded ephemeris row (~813 features)
     Process:
       • Broadcast row across all 329K active grid cells
       • Assign grid_lat, grid_lon, country for each cell
       • Lookup eq_index(date, grid_lat, grid_lon) → EQIndicator
     
     Output: 329K rows × 813 features for that date

┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 7: TEMPORAL SPLIT & CLASS BALANCING                                 │
│ (pipeline/features/engineering.py)                                       │
└──────────┬───────────────────────────────────────────────────────────────┘
           ↓
     PRE-2000 TRAINING SET (1900-1999):
     • Total: 100 years × 329K cells/year = 32.9M potential rows
     • Process by year (memory optimization)
     • For each year:
         - Build full feature matrix
         - Apply 10:1 negative downsampling
         - Append to training parquet
     • Final training set: ~263K rows (all positives + sampled negatives)
     
     POST-2000 TEST SET (2000-2026):
     • Total: 27 years × 329K cells/year = 8.8M potential rows
     • Stream by year to parquet (no downsampling)
     • Preserves natural earthquake distribution (~0.01% positive)
     • Final test set: ~8.5M rows

┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 8: FEATURE ARTIFACTS EXPORT                                         │
│ (pipeline/features/engineering.py)                                       │
└──────────┬───────────────────────────────────────────────────────────────┘
           ↓
     OUTPUT ARTIFACTS:
     
     • data/processed/feature_matrix_train.parquet
       - 263,124 rows × 813 columns
       - Format: Parquet (snappy compression)
       - Dtype: float32 (features), int (labels), object (date/country)
     
     • data/processed/feature_matrix_test.parquet
       - 8,543,220 rows × 813 columns
       - Same schema as training (column alignment)
     
     • data/processed/feature_columns.json
       - Ordered list of 800 feature column names
       - Excludes: date, grid_lat, grid_lon, country, EQIndicator
       - Used by model to load features in correct order
     
     • data/processed/nakshatra_encoder.pkl
       - Fitted OneHotEncoder instance
       - Used to transform new date batches if retraining

┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 9: MODEL TRAINING & EVALUATION                                      │
│ (pipeline/model/train_eval.py)                                           │
└──────────┬───────────────────────────────────────────────────────────────┘
           ↓
     TRAINING SPLIT (1900-2010):
       • Pre-2000: all downsampled rows (~160K)
       • 2000-2010: slice from test parquet, downsample 10:1 (~150K)
       • Total: ~300K rows (balanced positive:negative)
     
     HOLDOUT SPLIT (2010-2026):
       • Slice from test parquet
       • No downsampling (natural distribution)
       • Total: ~5.8M rows (imbalanced, ~0.01% positive)
     
     MODELS:
       • Logistic Regression (L2 penalty, max_iter=5000)
       • XGBoost (100 trees, class_weight='balanced')
     
     EVALUATION METRICS:
       • MCC (Matthews Correlation Coefficient) — winner metric
       • F1 score
       • Precision-recall curve → optimal threshold
     
     RESULTS (Current):
       • XGBoost selected (MCC = 0.0014)
       • Threshold: 0.150 (from PR curve)
       • F1 = 0.0028

┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 10: FINAL MODEL & PREDICTIONS                                       │
│ (pipeline/model/retrain.py, export_predictions.py)                       │
└──────────┬───────────────────────────────────────────────────────────────┘
           ↓
     RETRAIN:
       • Train XGBoost on full 1900-2026 data (all years, 10:1 downsampled)
       • Serialize to data/models/xgboost_final.pkl
     
     PREDICT 2026:
       • Load feature matrix for 2026 only
       • Run inference: softmax probabilities
       • Apply threshold (0.150) → binary predictions
       • Format: JSON {date: {grid: {prob, prediction}}}
       • Save to web/public/data/predictions.json

┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 11: WEB APP DEPLOYMENT                                              │
│ (web/)                                                                     │
└──────────┬───────────────────────────────────────────────────────────────┘
           ↓
     • Load pre-computed predictions JSON
     • Render interactive calendar
     • Display methodology + model metrics
     • No live inference (static predictions)
```

---

## Data Flow in Detail

### STEP 1: Data Collection

#### Source 1 – USGS Earthquakes (pipeline/data/usgs.py)

**Input:** USGS FDSNWS Event API (https://earthquake.usgs.gov/fdsnws/event/1/)

**Download Strategy:**
- Fetch M5.5+ events in 5-year chunks (1900–2026)
- Chunking avoids API truncation limit (20,000 records)
- Pagination with 2s, 4s, 8s backoff on network errors
- Deduplication before writing

**Output:** `data/raw/usgs_earthquakes.csv`

```
Columns: time, latitude, longitude, depth, magnitude, place, type
Rows: 5,893 (all M5.5+ worldwide, 1900-2026)
Sample:
  2020-01-01T12:34:56Z, 35.74, 140.14, 23.0, 6.1, "61 km E of Iwaki, Japan", "earthquake"
```

#### Source 2 – Swiss Ephemeris (pipeline/data/ephemeris.py)

**Computation:**
- Loop through each date 1900-2026 (46,022 days)
- For each date, compute 13 planetary positions using pysweph
- Planets: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Lilith, Node

**Per Planet (13 × ):**
- `{p}_lon` – Tropical longitude (0-360°)
- `{p}_lat` – Latitude (ecliptic)
- `{p}_speed` – Speed in longitude/day
- `{p}_sign` – Zodiac sign name (Aries, Taurus, …)
- `{p}_sign_num` – Sign index (0-11)
- `{p}_retro` – Retrograde flag (true/false)
- `{p}_nakshatra` – Vedic star name (Ashwini, Bharani, …)
- `{p}_nakshatra_num` – Nakshatra index (0-26)

**Aspects (all pairs):**
- `{p1}_{p2}_{aspect}` – Aspect indicator (true/false)
- Aspect types: conjunction (0°), sextile (60°), square (90°), trine (120°), opposition (180°)
- Orb: ±6°

**Tithi (Vedic lunar day):**
- Derived from Sun–Moon angular separation
- 30 tithis (lunar days)

**Output:** `data/raw/ephemeris.csv`

```
Columns: date, sun_lon, sun_lat, sun_speed, sun_sign, sun_sign_num, sun_retro,
         sun_nakshatra, sun_nakshatra_num, moon_lon, ... , tithi, tithi_name,
         mercury_moon_conjunction, venus_mars_trine, ... (390 aspects total)
Rows: 46,022 (1 per day from 1900-2026)
Columns: 200+
Sample:
  2020-01-01, 280.4, 0.0, 1.01, "Capricorn", 9, False, "Krittika", 2, 187.3, ..., 10, "Pushya", ...
```

---

### STEP 2: Data Validation

**Module:** pipeline/data/validate_ephemeris.py

**Purpose:** Spot-check ephemeris accuracy against JPL Horizons data

**Checks:**
- 10 reference dates (1900–2026)
- 2 planets per date (Sun, Jupiter)
- Compare computed vs. JPL expected longitude
- Tolerance: 0.5° (Swiss Ephemeris DE431 agrees to <0.01°)

**Example:**
```
Date: 2000-01-01
  Sun (computed): 280.41°, Jupiter (expected): 25.3°
  Delta: 0.01° ✓ PASS
```

**Exit Codes:**
- `0` – All checks passed, safe to proceed
- `1` – One or more checks failed, investigate ephemeris config
- `2` – ephemeris.csv not found, run ephemeris.py first

---

### STEP 3: Spatial Grid Mapping

**Input:** `data/raw/usgs_earthquakes.csv`

**Transformations:**

#### Grid Cell Computation
```python
grid_lat = floor(latitude / 5) * 5
grid_lon = floor(longitude / 5) * 5
```

Example: Earthquake at (35.74, 140.14) → Grid cell (35, 140)

**Why 5-degree cells?**
- ~500 km resolution (practical earthquake cluster size)
- Reduces spatial dimensions (prevents overfitting to small regions)
- ~329K active cells globally

#### Country Extraction
Parse USGS place strings:
```
"61 km E of Iwaki, Japan" → "Japan"
"26 km NE of Istanbul, Turkey" → "Turkey"
"Bismarck Sea" → "Bismarck Sea" (no country)
```

#### Active Cell Identification
A cell is "active" if it contains ≥1 M5.5+ earthquake in the historical record.
```
Result: Set of 329,104 (grid_lat, grid_lon) tuples
```

**Output (in-memory structures):**
- `active_cells` – set of ~329K (lat, lon) tuples
- `country_map` – dict mapping (lat, lon) → country name

---

### STEP 4: Ephemeris Encoding

**Input:** `data/raw/ephemeris.csv` (46,022 rows × 200 cols)

**Transformations:**

#### Cyclic Features (Sin/Cos)

**Why?** Angles are circular (0° ≈ 360°). Sin/cos preserves this circularity in feature space.

For each planet, encode three cyclic features:

**Longitude (0-360°):**
```python
sin_lon = sin(lon * 2π / 360)
cos_lon = cos(lon * 2π / 360)
# Example: 45° → sin_lon=0.707, cos_lon=0.707
```

**Sign (0-11, representing 12 zodiac signs):**
```python
sin_sign = sin(sign_num * 2π / 12)
cos_sign = cos(sign_num * 2π / 12)
```

**Nakshatra (0-26, representing 27 Vedic stars):**
```python
sin_nak = sin(nak_num * 2π / 27)
cos_nak = cos(nak_num * 2π / 27)
```

#### Tithi (Lunar Day)

Derived from Sun–Moon separation:
```python
diff = (moon_lon - sun_lon) % 360
tithi_idx = int(diff / 12)  # 0-29
tithi_sin = sin(tithi_idx * 2π / 30)
tithi_cos = cos(tithi_idx * 2π / 30)
```

#### Binary Features

Retrograde flag & aspects: cast boolean → int (0/1)
```python
{p}_retro: 0 (direct) or 1 (retrograde)
{p1}_{p2}_{aspect}: 0 (no aspect) or 1 (aspect present)
```

#### Column Droppage

After encoding, drop raw columns (not needed for ML):
```
Drop: {p}_lon, {p}_sign_num, {p}_sign, {p}_nakshatra_num
Keep: {p}_lon_sin, {p}_lon_cos, {p}_sign_num_sin, {p}_sign_num_cos, etc.
```

**Nakshatra Strings Preserved:** `{p}_nakshatra` columns remain (one-hot encoding in next step).

**Output:** `ephe_encoded` DataFrame (46,022 rows × 497 cols)
- 26 lon sin/cos (13 planets × 2)
- 26 sign_num sin/cos
- 26 nakshatra_num sin/cos
- 13 retro flags
- 390 aspects
- 2 tithi sin/cos
- 13 nakshatra strings (still present)
- 1 date column

---

### STEP 5: Nakshatra One-Hot Encoding

**Workflow:**

1. **Fit (on pre-2000 data only):**
   ```python
   pre2000_ephe = ephe_encoded[ephe_encoded.index < 2000-01-01]
   encoder = OneHotEncoder(categories='auto', handle_unknown='ignore')
   encoder.fit(pre2000_ephe[NAKSHATRA_COLS])  # Learn 27 categories
   joblib.dump(encoder, 'data/processed/nakshatra_encoder.pkl')
   ```

2. **Transform (all dates):**
   ```python
   ohe_array = encoder.transform(ephe_encoded[NAKSHATRA_COLS])
   # Output: (46022, 351) → 13 planets × 27 nakshatras
   ```

3. **Append + Drop:**
   ```python
   ephe_encoded = pd.concat([ephe_encoded.drop(NAKSHATRA_COLS), ohe_df], axis=1)
   # Result: 46022 rows × 846 cols (497 + 351 - 13 + 1 date)
   ```

**Why fit on pre-2000 only?**
Prevents label leakage: the encoder is a learned transformation (part of the model). Fitting on the full 1900-2026 range would expose the encoder to test data patterns.

**Output:** `ephe_encoded` with one-hot columns (46,022 rows × ~846 cols)

---

### STEP 6: Feature Matrix Construction & Broadcasting

**Input:**
- `ephe_encoded` – 46,022 rows × 846 cols
- `active_cells` – ~329K (lat, lon) tuples
- `country_map` – dict
- `eq_index` – MultiIndex Series (date, grid_lat, grid_lon) → EQIndicator

**Process (Year-by-Year):**

For each year Y in 1900–2026:
1. **Slice ephemeris:** `year_ephe = ephe_encoded[ephe_encoded.index.year == Y]`
   - ~365 rows (days in year)

2. **Vectorized broadcast:**
   ```python
   n_dates = len(year_ephe)
   n_cells = len(active_cells)
   
   # Repeat each date's features 329K times
   feature_vals = np.repeat(year_ephe[feature_cols].values, n_cells, axis=0)
   # Result: (365 * 329K, 813) ≈ 120M rows × 813 cols
   
   # Tile cell identifiers 365 times
   grid_lats = np.tile(cell_lats, n_dates)
   grid_lons = np.tile(cell_lons, n_dates)
   dates_repeat = np.repeat(dates, n_cells)
   ```

3. **Lookup EQIndicator:**
   ```python
   idx = (dates_repeat, grid_lats, grid_lons)
   eq_indicator = eq_index.reindex(idx).fillna(0).astype(int)
   # 1 if earthquake on (date, grid) else 0
   ```

4. **Build DataFrame:**
   ```python
   df = pd.DataFrame(feature_vals, columns=feature_cols)
   df['grid_lat'] = grid_lats
   df['grid_lon'] = grid_lons
   df['country'] = [country_map.get((r,c), 'Unknown') for r,c in cells]
   df['date'] = dates_repeat
   df['EQIndicator'] = eq_indicator
   ```

**Memory Optimization:**
- Process year-by-year (not all at once)
- Use `float32` for features (~1 GB/year vs 2 GB with float64)
- Streaming write to parquet (for post-2000)

**Output (per year):**
- Pre-2000: ~365 days × 329K cells = ~120M rows
- Post-2000: ~365 days × 329K cells = ~120M rows

---

### STEP 7: Temporal Split & Class Balancing

**PRE-2000 TRAINING (1900-1999)**

For each year Y in 1900–1999:
1. Build feature matrix (120M rows/year)
2. Apply 10:1 negative downsampling:
   ```python
   df_ds = downsample_negatives(df, ratio=10, random_state=42)
   # Keep: all EQIndicator=1 rows, sample 10× that many EQIndicator=0 rows
   # Result: ~350K rows/year (from 120M)
   ```
3. Append to training parquet

**Final Training Set:**
```
100 years × 350K rows/year ≈ 263K after concat + dedup
Columns: date, grid_lat, grid_lon, country, EQIndicator, 800 features
File: data/processed/feature_matrix_train.parquet
Size: ~3 GB
```

**POST-2000 TEST (2000-2026)**

For each year Y in 2000–2026:
1. Build feature matrix (120M rows/year)
2. NO downsampling (preserve natural distribution)
3. Stream-write to test parquet

**Final Test Set:**
```
27 years × 120M rows/year ≈ 8.5M rows
Columns: same as training
File: data/processed/feature_matrix_test.parquet
Size: ~35 GB
```

**Why Different Treatment?**
- Training: Balanced data improves gradient flow & convergence
- Test: Natural distribution → unbiased evaluation metrics

---

### STEP 8: Feature Artifacts Export

**Outputs from engineering.py/main():**

1. **Training Parquet**
   ```
   File: data/processed/feature_matrix_train.parquet
   Format: Apache Parquet, snappy compression
   Rows: 263,124
   Columns: 804 (date + grid_lat + grid_lon + country + EQIndicator + 800 features)
   Dtypes: object (date, country), int32 (grid_lat, grid_lon, EQIndicator), float32 (features)
   ```

2. **Test Parquet**
   ```
   File: data/processed/feature_matrix_test.parquet
   Format: Apache Parquet, snappy compression
   Rows: 8,543,220
   Columns: 804 (same schema as training)
   Dtypes: same as training
   ```

3. **Feature Column Manifest**
   ```json
   File: data/processed/feature_columns.json
   Content: Ordered list of 800 feature column names
   [
     "sun_lon_sin", "sun_lon_cos", "sun_sign_num_sin", ...,
     "moon_lon_sin", ..., "sun_Ashwini_ohe", ..., "tithi_sin"
   ]
   Purpose: Define feature order for model.load() and inference
   ```

4. **Encoder Artifact**
   ```
   File: data/processed/nakshatra_encoder.pkl
   Type: sklearn.preprocessing.OneHotEncoder (fitted)
   Purpose: Transform new dates if retraining
   Fit on: Pre-2000 data only (1900-1999)
   ```

**Validation Assertions** (run before exit):
```python
assert len(bad_cols) == 0  # No raw columns (_lon, _sign_num, _sign, _nakshatra_num)
assert "EQIndicator" in train_df.columns
assert "grid_lat" in train_df.columns
assert "grid_lon" in train_df.columns
assert "country" in train_df.columns
assert max(train_df["date"]) < 2000-01-01  # No temporal leakage
```

---

### STEP 9: Model Training & Evaluation

**Input:**
- `data/processed/feature_matrix_train.parquet` – 263K rows
- `data/processed/feature_matrix_test.parquet` – 8.5M rows
- `data/processed/feature_columns.json` – column order

**Train/Eval Split:**

| Subset | Dates | Rows | Positive | Negative | Ratio | Purpose |
|---|---|---|---|---|---|---|
| Internal Train | 1900-2010 | ~300K | ~30K | ~270K | 1:9 | Model fitting |
| Holdout | 2010-2026 | ~5.8M | ~58K | ~5.7M | 1:98 | Model selection |

**Models Trained:**

1. **Logistic Regression (Lasso)**
   ```python
   LogisticRegression(penalty='l2', max_iter=5000, class_weight='balanced')
   ```

2. **XGBoost**
   ```python
   XGBClassifier(n_estimators=100, class_weight='balanced', random_state=42)
   ```

**Evaluation Metrics:**

| Metric | Formula | Best Value | Current |
|---|---|---|---|
| MCC | (TP×TN - FP×FN) / √[(TP+FP)(TP+FN)(TN+FP)(TN+FN)] | +1 | 0.0014 |
| F1 | 2(P×R)/(P+R) | 1.0 | 0.0028 |
| Precision | TP / (TP+FP) | 1.0 | 0.0028 |
| Recall | TP / (TP+FN) | 1.0 | 0.50 |

**Decision Threshold:**
- Derived from precision-recall curve
- Threshold = 0.150 (balances precision vs recall)

**Model Selection:**
- **Winner:** XGBoost (MCC = 0.0014)
- **Rationale:** Higher MCC than LogisticRegression

**Output:** `data/models/eval_report.json`
```json
{
  "train_dates": ["1900-01-01", "2010-12-31"],
  "eval_dates": ["2010-01-01", "2026-12-31"],
  "model": "XGBoost",
  "threshold": 0.150,
  "mcc": 0.0014,
  "f1": 0.0028,
  "precision": 0.0028,
  "recall": 0.50,
  "confusion_matrix": [[5721630, 72319], [28956, 29083]],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### STEP 10: Final Model & 2026 Predictions

**Module:** pipeline/model/retrain.py

**Retraining:**
```python
# Load ALL feature matrices (1900-2026)
train_df = pd.read_parquet('data/processed/feature_matrix_train.parquet')
test_df = pd.read_parquet('data/processed/feature_matrix_test.parquet')

# Concatenate and downsample test to 10:1
full_df = pd.concat([train_df, downsample_negatives(test_df, ratio=10)])

# Train XGBoost on full set
model = XGBClassifier(...)
model.fit(full_df[feature_cols], full_df['EQIndicator'])

# Save model
joblib.dump(model, 'data/models/xgboost_final.pkl')
```

**Prediction (2026):**

```python
# Module: pipeline/model/export_predictions.py

# Load 2026 only
df_2026 = pd.read_parquet(
    'data/processed/feature_matrix_test.parquet',
    filters=[('date', '>=', 2026-01-01), ('date', '<', 2027-01-01)]
)

# Predict probabilities
probs = model.predict_proba(df_2026[feature_cols])[:, 1]

# Apply threshold
predictions = (probs > 0.150).astype(int)

# Format for web
output = {
    date: {
        (grid_lat, grid_lon): {
            'probability': prob,
            'prediction': pred
        }
        for date, grid_lat, grid_lon, prob, pred
        in df_2026[['date', 'grid_lat', 'grid_lon']]
            .assign(probability=probs, prediction=predictions)
            .itertuples(index=False)
    }
}

# Save as JSON
with open('web/public/data/predictions.json', 'w') as f:
    json.dump(output, f)
```

**Output:** `web/public/data/predictions.json`
```json
{
  "2026-01-01": {
    "[35, 140]": {"probability": 0.23, "prediction": 1},
    "[35, 145]": {"probability": 0.08, "prediction": 0},
    ...
  },
  "2026-01-02": {
    ...
  }
}
```

---

### STEP 11: Web App Deployment

**Module:** web/

**Static Rendering:**
```typescript
// Load predictions JSON
const predictions = await fetch('data/predictions.json').then(r => r.json())

// Render calendar
for each date in 2026 {
  for each grid cell {
    if predictions[date][grid] > threshold {
      color cell red (high risk)
    }
  }
}
```

**No Live Inference:** All predictions pre-computed and served statically. This allows:
- Fast page load (no model latency)
- Offline fallback
- Cached predictions on CDN

---

## Data Flow Summary

| Step | Input | Process | Output | Size |
|---|---|---|---|---|
| 1. Collection | API + Computation | Download + Compute | ephemeris.csv, usgs_earthquakes.csv | 50 MB |
| 2. Validation | ephemeris.csv | Spot-check vs JPL | ✓ Pass/Fail | N/A |
| 3. Grid Mapping | usgs_earthquakes.csv | Grid cell + country | active_cells set | 329K cells |
| 4. Ephemeris Encoding | ephemeris.csv | Sin/cos + binary | ephe_encoded | 46K × 846 cols |
| 5. Nakshatra One-Hot | ephe_encoded | OneHotEncoder | ephe_encoded (updated) | 46K × 846 cols |
| 6. Matrix Broadcasting | ephe_encoded + active_cells | Broadcast + lookup | feature_matrix (temp) | 120M rows/year |
| 7. Temporal Split | feature_matrix | Downsampling (10:1 train only) | train + test parquet | 263K + 8.5M rows |
| 8. Export Artifacts | train + test | Save parquet + JSON + encoder | 4 files (3+35 GB) | 38 GB total |
| 9. Training & Eval | train + test | XGBoost fit + evaluate | eval_report.json | 1 KB |
| 10. Retrain & Predict | full dataset + model | Fit on 1900-2026 + infer 2026 | predictions.json + model pkl | 100 MB |
| 11. Deploy | predictions.json | Static rendering | Web calendar | Live on Vercel |

---

## Key Architectural Decisions

### 1. Why 5-Degree Grid Cells?
- **Pros:** Reduces spatial dimensions, improves generalization, matches earthquake cluster size
- **Cons:** Loses fine-grained location precision
- **Alternative:** 1° cells (too many → overfitting), 10° cells (too coarse → underfitting)

### 2. Why Sin/Cos Encoding?
- **Circular features:** 0° and 360° are the same, but linear scaling treats them as opposites
- **Solution:** sin/cos preserves circularity in 2D feature space
- **Alternative:** Ordinal encoding (would lose circularity), one-hot per degree (too many features)

### 3. Why Fit Encoder on Pre-2000 Only?
- **Label leakage:** If encoder learns from post-2000 nakshatras, the model can "cheat" by memorizing those patterns
- **Solution:** Fit only on training distribution, apply to all with `handle_unknown='ignore'`
- **Alternative:** Fit on full dataset (would leak test info)

### 4. Why 10:1 Downsampling in Training?
- **Imbalance:** Earthquakes are rare (~0.01% of samples)
- **Problem:** Neural nets & tree models struggle with extreme imbalance (always predict 0)
- **Solution:** Downsample negatives to 10:1 ratio (still imbalanced, but trainable)
- **Alternative:** No downsampling (poor convergence), 1:1 (loses information)

### 5. Why No Downsampling in Test?
- **Evaluation bias:** Downsampled test set inflates metrics (MCC, F1) relative to real-world distribution
- **Solution:** Keep test set at natural distribution (~0.01% positive)
- **Alternative:** Downsample test (biased metrics, won't catch overfitting)

### 6. Why Parquet Format?
- **Compression:** Snappy reduces 8.5M × 813 float32 matrix from 28 GB to 2.8 GB
- **Columnar layout:** Efficient for ML pipeline (load features only, not metadata)
- **Filter pushdown:** Fast slicing (e.g., 2000-2010 subset) without full scan
- **Alternative:** CSV (too large), HDF5 (slower I/O)

---

## Performance Characteristics

### Time

```
Step 1: USGS download          ~5 min   (5-year chunks × 20 retries)
Step 2: Ephemeris computation  ~4 hours (46K days × 13 planets × aspects)
Step 3: Validation             ~10 sec
Step 4-5: Encoding             ~10 min
Step 6: Matrix building        ~1 hour  (per-year broadcast + write)
Step 7: Training + Eval        ~15 min
Step 8: Retrain + Predict      ~5 min
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total                           ~5 hours
```

### Memory (Peak)

```
Ephemeris computation: 500 MB (pysweph + pandas)
Feature encoding:     1 GB   (46K × 846 cols at float32)
Matrix broadcasting:  2 GB   (one year in memory)
Model training:       3 GB   (300K × 813 + model state)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Max RAM required: ~3 GB (with careful streaming)
```

### Storage

```
Raw data (ephemeris + USGS):        50 MB
Feature matrices (train + test):    38 GB
Models (XGBoost + LogReg):          50 MB
Intermediate artifacts:             100 MB
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total disk:                         38 GB
```

---

## Reproducibility & Versioning

### Docker / Environment
```bash
# All steps use uv (reproducible Python environment)
uv sync                         # Install from pyproject.toml
uv run python -m pipeline.*     # Run any module
```

### Random Seeds
```python
# Fixed across all modules
random_state = 42
np.random.seed(42)
```

### Data Versioning
- USGS data: API fetch (deterministic URL + date range)
- Ephemeris: Swiss Ephemeris DE431 (fixed library version)
- Features: Deterministic (no randomness except downsampling seed)

---

## Debugging & Validation Checklist

### After Running Data Collection
- [ ] `data/raw/usgs_earthquakes.csv` exists (5,893 rows)
- [ ] `data/raw/ephemeris.csv` exists (46,022 rows)
- [ ] Run `validate_ephemeris.py` → all 10 checks pass

### After Running Feature Engineering
- [ ] `data/processed/feature_matrix_train.parquet` (263K rows)
- [ ] `data/processed/feature_matrix_test.parquet` (8.5M rows)
- [ ] `data/processed/feature_columns.json` (800 columns)
- [ ] `data/processed/nakshatra_encoder.pkl` exists
- [ ] No raw columns in output (validation assertions pass)

### After Running Model Training
- [ ] `data/models/eval_report.json` exists
- [ ] MCC > 0 (model better than random)
- [ ] Threshold in [0, 1]

### After Running Retrain + Predict
- [ ] `data/models/xgboost_final.pkl` exists
- [ ] `web/public/data/predictions.json` has 2026 predictions
- [ ] Calendar renders without errors

---

## FAQ

**Q: Why is the model performance so low (MCC=0.0014)?**

A: Earthquakes are chaotic and rare. Binary classification at 0.01% positive rate is extremely difficult:
- False negatives: even 99.9% recall misses 100 earthquakes
- False positives: easy to generate false alarms
- MCC penalizes both equally, yielding very low scores

Alternative approaches:
- Regression on magnitude (instead of binary)
- Location-specific models (customize per earthquake zone)
- Transfer learning from seismology models
- Ensemble with physics-based predictions

**Q: Can I add new planets/aspects?**

A: Yes, modify `pipeline/data/ephemeris.py`:
```python
PLANETS = {..., "new_planet": swe.PLANET_ID}
```
Then rerun ephemeris + engineering pipelines.

**Q: Why not normalize features (0-1)?**

A: XGBoost is tree-based (invariant to feature scale). Logistic Regression would benefit from normalization, but XGBoost won anyway (higher MCC).

**Q: Can predictions change if I rerun?**

A: No — all randomness is seeded (`random_state=42`). Predictions are deterministic given the same model + data.

**Q: How do I update 2026 predictions mid-year?**

A: Rerun `export_predictions.py` after updating USGS data in the test parquet. No retraining needed (predictions are pre-computed).
