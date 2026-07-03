# Feature Engineering Pipeline

This module transforms raw ephemeris and earthquake data into machine-learning-ready feature matrices. It's the core of Phase 2 of the Earthquake Astrology project.

## Overview

The feature engineering pipeline orchestrates a complete end-to-end transformation:

```
Raw Data (ephemeris.csv, usgs_earthquakes.csv)
    ↓
Grid Cell Mapping & Country Extraction
    ↓
Ephemeris Encoding (cyclic transforms, nakshatra one-hot)
    ↓
Feature Matrix Broadcasting (across grid cells × dates)
    ↓
Output Artifacts (parquet, encoder, column manifest)
```

**Output artifacts:**
- `data/processed/feature_matrix_train.parquet` – ~263K rows (pre-2000, 10:1 downsampled)
- `data/processed/feature_matrix_test.parquet` – ~8.5M rows (post-2000, all events)
- `data/processed/feature_columns.json` – Ordered list of feature column names
- `data/processed/nakshatra_encoder.pkl` – Fitted OneHotEncoder (fit on pre-2000 only)

---

## Key Concepts

### Grid Cells
The Earth is divided into **5-degree grid cells** (e.g., 35°N×(-125°)E). Each earthquake location is mapped to its nearest grid cell using:

```python
grid_lat = floor(lat / 5) * 5
grid_lon = floor(lon / 5) * 5
```

**Why?** Reduces spatial resolution to ~500 km cells, improving generalization and computational efficiency.

### Active Cells
Only grid cells containing at least one M5.5+ earthquake (in the historical record) are included in the feature matrix. Non-active cells are skipped entirely, dramatically reducing the output size.

**Example:** ~329K active cells globally from the USGS dataset.

### Temporal Split
The project enforces a **hard temporal boundary at 2000-01-01**:
- **Training:** 1900–1999 (pre-2000)
- **Test:** 2000–2026 (post-2000)

This prevents temporal leakage and ensures the model learns long-term patterns without recent data bias.

### Country Mapping
Each grid cell is assigned the most common country name in its region (extracted from USGS place strings). Used for interpretability, not model features.

---

## Feature Engineering Steps

### 1. **Grid & Country Setup**

Functions:
- `compute_grid_coords(lat, lon)` → `(grid_lat, grid_lon)`
- `build_active_cells(usgs_df)` → set of active cell tuples
- `build_country_map(usgs_df)` → dict mapping cells to country names

**Input:** Raw USGS data with latitude/longitude/place.

### 2. **Earthquake Index Construction**

Function: `build_eq_index(usgs_df)`

Creates a **MultiIndex Series** with:
- **Index:** `(date, grid_lat, grid_lon)`
- **Value:** `1` for cells with at least one qualifying earthquake on that date

**Purpose:** Fast O(1) lookup during matrix broadcasting.

### 3. **Ephemeris Encoding**

Function: `encode_ephemeris(ephe_df)`

Raw ephemeris columns are transformed into ML-ready features:

#### Per-Planet Cyclic Encoding
For each of the 13 planets (Sun, Moon, Mercury, ..., Lilith, Node):

| Raw Column | Encoding | Output Columns | Period |
|---|---|---|---|
| `{p}_lon` | sin/cos | `{p}_lon_sin`, `{p}_lon_cos` | 360° |
| `{p}_sign_num` | sin/cos | `{p}_sign_num_sin`, `{p}_sign_num_cos` | 12 signs |
| `{p}_nakshatra_num` | sin/cos | `{p}_nakshatra_num_sin`, `{p}_nakshatra_num_cos` | 27 nakshatras |
| `{p}_retro` | cast to int | `{p}_retro` | N/A (binary) |

**Why sin/cos?** Cyclical features (e.g., longitude) wrap around (0° ≈ 360°). Sin/cos transforms preserve this circularity for neural networks.

#### Tithi (Vedic Lunar Day)
Derived from Sun and Moon longitudes:

```python
tithi_idx = floor((moon_lon - sun_lon) % 360 / 12)  # 0–29
```

Output: `tithi_sin`, `tithi_cos`

#### Aspects
All aspect columns (`{p1}_{p2}_{aspect_type}`) converted from boolean to int (0/1).
- Aspect types: conjunction, opposition, trine, square, sextile
- Total: ~390 aspect columns (13 planets × 12 pairs × ~2.5 aspects avg)

#### Nakshatra (Vedic Star)
Raw string columns (`{p}_nakshatra`) are **preserved** at this step for one-hot encoding in the next step.

---

### 4. **Nakshatra One-Hot Encoding**

Functions:
- `fit_nakshatra_encoder(pre2000_df)` – Fit sklearn OneHotEncoder on pre-2000 training data
- `apply_nakshatra_encoding(df, encoder)` – Transform 13 nakshatra strings to 351 one-hot columns

**Why fit on pre-2000 only?** Ensures the encoder learns only from training data, avoiding label leakage.

**Output:** 27 nakshatras × 13 planets = 351 binary columns (uint8).

---

### 5. **Feature Matrix Broadcasting**

Function: `build_matrix_year(year_ephe, active_cells, eq_index, country_map)`

For each date in the ephemeris:
1. **Broadcast** the encoded ephemeris row to all active grid cells
2. **Assign EQIndicator:** 1 if `(date, grid_lat, grid_lon)` exists in eq_index, else 0

**Example:**
```
Input:  1 ephemeris row (2020-01-01) × 329K active cells
        = 329K output rows, each with the same ephemeris features + unique grid cell
Output: [date, grid_lat, grid_lon, country, EQIndicator, all ephemeris features]
```

**Memory optimization:** Uses vectorized numpy operations (repeat/tile) instead of Python loops.

---

### 6. **Temporal Leakage Guard**

Function: `assert_no_temporal_leakage(train_dates, test_dates)`

Asserts:
- `max(train_dates) < 2000-01-01`
- `min(test_dates) >= 2000-01-01`

Raises `AssertionError` if the split is violated.

---

### 7. **Negative Downsampling**

Function: `downsample_negatives(df, ratio=10, random_state=42)`

Earthquakes are rare events (~0.01% of grid cells × date combinations). To balance the dataset:
- **All positive rows (EQIndicator=1)** are preserved
- **Negative rows (EQIndicator=0)** are randomly sampled to achieve `ratio:1` (e.g., 10:1)

**Applied:** Only to pre-2000 training data; test data is NOT downsampled (preserves natural distribution).

**Result:** ~263K training rows (from 100M+) while maintaining balance.

---

## Module Structure

```
pipeline/features/
├── __init__.py              # Module entry point (minimal)
└── engineering.py           # All feature engineering logic
```

### Main Components in `engineering.py`

#### Constants
- `PLANETS` – 13 celestial bodies
- `SIGN_NAMES` – 12 Zodiac signs
- `NAKSHATRAS` – 27 Vedic stars
- `TITHIS` – 30 lunar days
- `NAKSHATRA_COLS` – Column names for nakshatra encoding

#### Grid & Country
- `compute_grid_coords()` – Map lat/lon to 5° grid
- `build_active_cells()` – Extract active cell set
- `extract_country()` – Parse USGS place strings
- `build_country_map()` – Create cell → country mapping

#### Index Building
- `build_eq_index()` – MultiIndex Series for fast EQ lookups

#### Encoding
- `encode_cyclic()` – Convert 0–360° (or period) to sin/cos
- `compute_tithi()` – Calculate lunar day from Sun/Moon
- `encode_ephemeris()` – Transform raw ephemeris to cyclic + aspect features

#### Nakshatra Encoding
- `fit_nakshatra_encoder()` – OneHotEncoder fit on pre-2000 data
- `apply_nakshatra_encoding()` – Apply one-hot transform
- `save_encoder()` / `load_encoder()` – Persist encoder to disk

#### Matrix Building
- `build_matrix_chunk()` – Single-date broadcaster (legacy, slower)
- `build_matrix_year()` – Vectorized year-batch broadcaster (preferred)
- `active_cells_list()` – Convert cell set to sorted list

#### Quality Assurance
- `assert_no_temporal_leakage()` – Guard against train/test contamination
- `downsample_negatives()` – Balance rare-event distribution

#### Orchestration
- `main()` – Execute full pipeline end-to-end

---

## How to Add New Features

### Option 1: Cyclic Feature (e.g., new angle)

1. **Add to `encode_ephemeris()`:**
   ```python
   # In the encoding loop
   sin_feat, cos_feat = encode_cyclic(df[f"{p}_new_angle"].astype(float), period=360.0)
   df[f"{p}_new_angle_sin"] = sin_feat.values
   df[f"{p}_new_angle_cos"] = cos_feat.values
   cols_to_drop.append(f"{p}_new_angle")  # Drop raw column
   ```

2. **Update tests** in `tests/test_engineering.py`.

### Option 2: Binary Feature (e.g., new flag)

1. **Add to `encode_ephemeris()`:**
   ```python
   df[f"{p}_new_flag"] = df[f"{p}_new_flag"].astype(int)
   # No sin/cos encoding; just cast to int
   ```

2. **Update tests.**

### Option 3: Categorical Feature (e.g., new planet attribute)

1. **Add OneHotEncoder logic** (similar to nakshatra):
   ```python
   def fit_new_encoder(pre2000_df):
       encoder = OneHotEncoder(...)
       encoder.fit(pre2000_df[["new_category"]])
       return encoder
   
   def apply_new_encoding(df, encoder):
       ohe_array = encoder.transform(df[["new_category"]])
       # ... build DataFrame from array, drop original column
   ```

2. **Call in `main()`** after `apply_nakshatra_encoding()`.

3. **Update tests.**

### Option 4: Grid/Temporal Feature

1. **Add to `build_matrix_year()`:**
   ```python
   df["new_temporal_feat"] = compute_feature_from_dates(dates)
   df["new_cell_feat"] = compute_feature_from_cells(active_cells)
   ```

2. **Update tests** to check that new columns appear in output.

---

## Pipeline Execution

### Run Full Pipeline

```bash
uv run python -m pipeline.features.engineering
```

**Logs:**
- Loads ephemeris & USGS data
- Fits nakshatra encoder on pre-2000
- Encodes full ephemeris (cyclic + one-hot)
- Builds pre-2000 training matrix (per-year downsample)
- Builds post-2000 test matrix (streaming write)
- Saves artifacts
- Validates output (no raw columns, assertions)

### Run Tests

```bash
uv run pytest tests/test_engineering.py -v
```

Tests cover:
- Grid cell computation
- Country extraction
- EQ index collapsing
- Encoding column inventory
- Temporal split validation
- Encoder fit scope
- Downsampling ratios

---

## Output Schema

### Training Matrix (Pre-2000)

| Column | Type | Description |
|---|---|---|
| `date` | object (date) | Ephemeris date |
| `grid_lat` | int | Grid cell latitude (5° resolution) |
| `grid_lon` | int | Grid cell longitude (5° resolution) |
| `country` | str | Most common country in cell |
| `EQIndicator` | int | 1=earthquake on this date/cell, 0=no |
| `{p}_lon_sin` | float32 | Encoded planet longitude (sine) |
| `{p}_lon_cos` | float32 | Encoded planet longitude (cosine) |
| `{p}_sign_num_sin` | float32 | Encoded zodiac sign (sine) |
| `{p}_sign_num_cos` | float32 | Encoded zodiac sign (cosine) |
| `{p}_nakshatra_num_sin` | float32 | Encoded nakshatra (sine) |
| `{p}_nakshatra_num_cos` | float32 | Encoded nakshatra (cosine) |
| `{p}_retro` | int | Retrograde flag (0/1) |
| `{p1}_{p2}_{aspect}` | int | Aspect indicator (0/1) |
| `tithi_sin` | float32 | Encoded lunar day (sine) |
| `tithi_cos` | float32 | Encoded lunar day (cosine) |
| `{p}_{nakshatra}_ohe` | uint8 | One-hot nakshatra columns (351 total) |

**Dimensions:** ~263K rows × 813 columns

### Test Matrix (Post-2000)

Same schema as training, but:
- No downsampling applied
- Natural earthquake distribution (~0.01% positive)
- ~8.5M rows

---

## Memory & Performance Notes

### Pre-2000 Training Matrix Construction
- **Raw matrix:** 100 years × ~329K cells/year × 813 features = ~210 GB
- **Per-year downsampling:** Process one year at a time, apply 10:1 negative downsample, write to parquet
- **Peak RAM:** ~1.5 GB (one year in memory)
- **Total output:** ~3 GB (263K rows × 813 cols after downsampling)

### Post-2000 Test Matrix Construction
- **Streaming write:** Build one year at a time, write immediately to parquet file
- **Peak RAM:** ~2 GB (one year in memory)
- **Total output:** ~35 GB (8.5M rows × 813 cols)

### Feature Dtype Optimization
- Numerical features cast to `float32` (vs float64) during broadcasting
- Saves ~50% memory during year-chunk processing

---

## Validation & Quality Assurance

### Assertions in `main()`
1. No raw columns in output (`_lon`, `_sign_num`, `_sign`, `_nakshatra_num`)
2. Required columns present (`EQIndicator`, `grid_lat`, `grid_lon`, `country`)
3. Temporal split respected (train < 2000-01-01, test >= 2000-01-01)

### Test Coverage (`tests/test_engineering.py`)

| Feature | Test Class | Status |
|---|---|---|
| Grid cells (`compute_grid_coords`, `build_active_cells`) | `TestGridCells` | ✓ Implemented |
| Country extraction (`extract_country`) | `TestCountryParsing` | ✓ Implemented |
| EQ index (`build_eq_index`) | `TestEQIndicator` | ✓ Implemented |
| Ephemeris encoding (cyclic transforms, aspects) | `TestCyclicalEncoding` | ✓ Implemented |
| Temporal split (`assert_no_temporal_leakage`) | `TestTemporalSplit` | ✓ Implemented |
| Encoder fit scope (pre-2000 only) | `TestEncoderFitScope` | ✓ Implemented |
| Downsampling (`downsample_negatives`) | `TestDownsamplingScope` | ✓ Implemented |

---

## Dependencies

- **numpy** – Vectorized array operations
- **pandas** – DataFrames and MultiIndex
- **scikit-learn** – OneHotEncoder for nakshatras
- **pyarrow** – Parquet I/O with compression
- **joblib** – Encoder serialization
- **tqdm** – Progress bars

---

## Links & References

- [VALIDATION.md](../../VALIDATION.md) – Detailed test requirements (FEAT-01 through FEAT-05)
- [pipeline/data/ephemeris.py](../data/ephemeris.py) – Raw ephemeris computation
- [pipeline/data/usgs.py](../data/usgs.py) – USGS data loading & filtering
- [tests/test_engineering.py](../../tests/test_engineering.py) – Test suite

---

## FAQ

**Q: Why sin/cos encoding for angles?**  
A: Cyclic features (0° ≈ 360°) don't have a natural linear ordering. Sin/cos preserves circularity for neural networks.

**Q: Why fit the nakshatra encoder only on pre-2000 data?**  
A: Prevents the encoder from "memorizing" post-2000 nakshatras. The encoder is part of the model's learned transformation.

**Q: Why 10:1 downsampling in training?**  
A: Earthquakes are rare (~0.01% of samples). 10:1 balancing improves gradient flow and model stability without losing information.

**Q: Why NOT downsample test data?**  
A: Test evaluation must reflect the natural distribution to avoid overly optimistic metrics.

**Q: Can I add custom features?**  
A: Yes! See "How to Add New Features" section above. Update `encode_ephemeris()` or add new encoding functions, then run `main()` and tests.

---

## Version History

- **Phase 2, Wave 0** – Initial pipeline scaffold (grid cells, country extraction, index building)
- **Phase 2, Wave 1** – Core encoding (cyclic, nakshatra, aspects, tithi)
- **Phase 2, Wave 2** – Matrix broadcasting & persistence (train/test split, downsampling, parquet output)
