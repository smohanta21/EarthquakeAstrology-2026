"""
pipeline/features/engineering.py

Feature engineering for the Earthquake Astrology project (Phase 2).

Provides:
  - Grid cell helpers (compute_grid_coords, build_active_cells)
  - Country extraction from USGS place strings (extract_country)
  - EQ index construction (build_eq_index)
  - Ephemeris encoding with cyclic transforms (encode_ephemeris, encode_cyclic)
  - Tithi computation (compute_tithi)
  - Nakshatra encoder (fit_nakshatra_encoder, apply_nakshatra_encoding)
  - Encoder persistence (save_encoder, load_encoder)
  - Temporal leakage guard (assert_no_temporal_leakage)
  - Negative downsampling (downsample_negatives)
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("pipeline.features.engineering")

# ---------------------------------------------------------------------------
# Constants — replicated from pipeline/data/ephemeris.py to avoid importing
# the swisseph C extension at test time (which requires .se1 files).
# ---------------------------------------------------------------------------

PLANETS = [
    "sun",
    "moon",
    "mercury",
    "venus",
    "mars",
    "jupiter",
    "saturn",
    "uranus",
    "neptune",
    "pluto",
    "chiron",
    "lilith",
    "node",
]

SIGN_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishtha",
    "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

# Tithi names: SP1..SP14, FM (full moon, idx 14), KP1..KP14, NM (new moon, idx 29)
TITHIS = (
    ["SP1", "SP2", "SP3", "SP4", "SP5", "SP6", "SP7",
     "SP8", "SP9", "SP10", "SP11", "SP12", "SP13", "SP14", "FM"]
    + ["KP1", "KP2", "KP3", "KP4", "KP5", "KP6", "KP7",
       "KP8", "KP9", "KP10", "KP11", "KP12", "KP13", "KP14", "NM"]
)

# Nakshatra string column names (one per planet)
NAKSHATRA_COLS = [f"{p}_nakshatra" for p in PLANETS]

# Aspect type suffixes used in ephemeris column naming
_ASPECT_TYPES = {"conjunction", "opposition", "trine", "square", "sextile"}


# ---------------------------------------------------------------------------
# Grid cell helpers
# ---------------------------------------------------------------------------


def compute_grid_coords(lat: float, lon: float) -> tuple[int, int]:
    """Map a (lat, lon) coordinate to the nearest 5-degree grid cell.

    Returns:
        (grid_lat, grid_lon) where grid_lat = floor(lat/5)*5, grid_lon = floor(lon/5)*5.
    """
    grid_lat = int(np.floor(lat / 5) * 5)
    grid_lon = int(np.floor(lon / 5) * 5)
    return (grid_lat, grid_lon)


def build_active_cells(usgs_df: pd.DataFrame) -> set[tuple[int, int]]:
    """Return the set of 5-degree grid cells that contain at least one M5.5+ event.

    Args:
        usgs_df: DataFrame with 'latitude' and 'longitude' columns.

    Returns:
        Set of (grid_lat, grid_lon) tuples.
    """
    grid_lats = (np.floor(usgs_df["latitude"].to_numpy() / 5) * 5).astype(int)
    grid_lons = (np.floor(usgs_df["longitude"].to_numpy() / 5) * 5).astype(int)
    cells = set(zip(grid_lats.tolist(), grid_lons.tolist()))
    logger.info(f"Active cells (all-time): {len(cells)}")
    return cells


# ---------------------------------------------------------------------------
# Country parsing
# ---------------------------------------------------------------------------


def extract_country(place: str | None) -> str:
    """Extract country from a USGS place string.

    Rules:
        - If place is None or empty string → return "Unknown"
        - If place contains a comma → return the last token after the final comma (stripped)
        - Otherwise → return place as-is (e.g. "Bismarck Sea")
    """
    import math
    if place is None:
        return "Unknown"
    if isinstance(place, float) and math.isnan(place):
        return "Unknown"
    place_str = str(place).strip()
    if not place_str:
        return "Unknown"
    if "," in place_str:
        return place_str.split(",")[-1].strip()
    return place_str


# ---------------------------------------------------------------------------
# EQ indicator index
# ---------------------------------------------------------------------------


def build_eq_index(usgs_df: pd.DataFrame) -> pd.Series:
    """Build a binary earthquake indicator Series indexed by (date, grid_lat, grid_lon).

    Each unique (date, cell) pair maps to 1, regardless of how many events occurred.

    Args:
        usgs_df: DataFrame with 'time' (datetime-parseable), 'latitude', 'longitude' columns.

    Returns:
        pd.Series with MultiIndex (date, grid_lat, grid_lon) and integer value 1.
    """
    from datetime import date as date_type

    times = pd.to_datetime(usgs_df["time"])
    dates = times.dt.date  # convert to datetime.date objects

    grid_lats = (np.floor(usgs_df["latitude"].to_numpy() / 5) * 5).astype(int).tolist()
    grid_lons = (np.floor(usgs_df["longitude"].to_numpy() / 5) * 5).astype(int).tolist()

    idx = pd.MultiIndex.from_arrays(
        [
            pd.Index(list(dates), dtype=object),
            grid_lats,
            grid_lons,
        ],
        names=["date", "grid_lat", "grid_lon"],
    )
    series = pd.Series(1, index=idx, dtype=int)
    # Collapse duplicate (date, cell) entries — keep one entry per unique key
    series = series[~series.index.duplicated(keep="first")]
    return series


def build_country_map(usgs_df: pd.DataFrame) -> dict:
    """Build a mapping from (grid_lat, grid_lon) to the most common country name.

    Args:
        usgs_df: DataFrame with 'latitude', 'longitude', 'place' columns.

    Returns:
        Dict mapping (grid_lat, grid_lon) tuple → country name string.
        Cells with no place data map to "Unknown".
    """
    grid_lats = (np.floor(usgs_df["latitude"].to_numpy() / 5) * 5).astype(int).tolist()
    grid_lons = (np.floor(usgs_df["longitude"].to_numpy() / 5) * 5).astype(int).tolist()

    tmp = pd.DataFrame({
        "grid_lat": grid_lats,
        "grid_lon": grid_lons,
        "country": usgs_df["place"].apply(extract_country).values,
    })

    # For each cell, use the most common country name
    country_map: dict = {}
    for (glat, glon), group in tmp.groupby(["grid_lat", "grid_lon"]):
        country_map[(int(glat), int(glon))] = group["country"].mode().iloc[0]

    return country_map


# ---------------------------------------------------------------------------
# Ephemeris encoding
# ---------------------------------------------------------------------------


def encode_cyclic(series: pd.Series, period: float) -> tuple[pd.Series, pd.Series]:
    """Encode a cyclic feature using sin/cos transformation.

    Args:
        series: Numeric Series (e.g. longitude 0-360, sign_num 0-11).
        period: The full period of the cycle (e.g. 360.0 for longitudes, 12.0 for signs).

    Returns:
        Tuple of (sin_series, cos_series).
    """
    radians = series * (2 * np.pi / period)
    return np.sin(radians), np.cos(radians)


def compute_tithi(sun_lon: float, moon_lon: float) -> tuple[int, str]:
    """Compute the Vedic lunar day (tithi) from sun and moon longitudes.

    Tithi = floor((moon_lon - sun_lon) % 360 / 12), values 0-29.

    Args:
        sun_lon: Sun tropical longitude (degrees 0-360).
        moon_lon: Moon tropical longitude (degrees 0-360).

    Returns:
        Tuple of (tithi_num 0-29, tithi_name str).
    """
    diff = (moon_lon - sun_lon) % 360
    tithi_idx = int(diff / 12)
    return tithi_idx, TITHIS[tithi_idx]


def encode_ephemeris(ephe_df: pd.DataFrame) -> pd.DataFrame:
    """Encode raw ephemeris DataFrame into ML-ready cyclic and binary features.

    Transformations applied per planet p in PLANETS:
        - {p}_lon      → {p}_lon_sin, {p}_lon_cos  (period=360)
        - {p}_sign_num → {p}_sign_num_sin, {p}_sign_num_cos  (period=12)
        - {p}_retro    → {p}_retro  (boolean cast to int)
        - {p}_nakshatra_num → {p}_nakshatra_num_sin, {p}_nakshatra_num_cos  (period=27)

    Additional:
        - tithi_sin, tithi_cos derived from sun_lon and moon_lon via compute_tithi
        - All aspect columns ({p1}_{p2}_{aspect}) converted to int (0/1)

    Raw columns removed (only these four groups):
        - {p}_lon (raw float)
        - {p}_sign_num (raw int)
        - {p}_sign (text)
        - {p}_nakshatra_num (raw int, replaced by sin/cos)

    PRESERVED:
        - {p}_nakshatra string columns — NOT dropped here.
          apply_nakshatra_encoding() (Plan 05) reads these and drops them after one-hot encoding.

    Args:
        ephe_df: Raw ephemeris DataFrame from pipeline/data/ephemeris.py.

    Returns:
        Encoded DataFrame with cyclic, binary, aspect columns, and nakshatra name strings.
        Column count: 26 lon sin/cos + 26 sign_num sin/cos + 26 nakshatra_num sin/cos
                      + 13 retro + 390 aspect + 2 tithi + 13 nakshatra strings = 496 + date
    """
    df = ephe_df.copy()

    # Compute tithi sin/cos from sun and moon longitudes (before dropping lon columns)
    sun_lons = df["sun_lon"].astype(float)
    moon_lons = df["moon_lon"].astype(float)

    # Vectorised tithi: diff = (moon - sun) % 360, idx = int(diff / 12)
    diff = (moon_lons - sun_lons) % 360.0
    tithi_idx = (diff / 12.0).astype(int)
    tithi_sin, tithi_cos = encode_cyclic(tithi_idx.astype(float), period=30.0)
    df["tithi_sin"] = tithi_sin.values
    df["tithi_cos"] = tithi_cos.values

    # Per-planet cyclic encoding
    cols_to_drop: list[str] = []
    for p in PLANETS:
        # Longitude (period=360)
        sin_lon, cos_lon = encode_cyclic(df[f"{p}_lon"].astype(float), period=360.0)
        df[f"{p}_lon_sin"] = sin_lon.values
        df[f"{p}_lon_cos"] = cos_lon.values
        cols_to_drop.append(f"{p}_lon")

        # Sign number (period=12)
        sin_sign, cos_sign = encode_cyclic(df[f"{p}_sign_num"].astype(float), period=12.0)
        df[f"{p}_sign_num_sin"] = sin_sign.values
        df[f"{p}_sign_num_cos"] = cos_sign.values
        cols_to_drop.append(f"{p}_sign_num")

        # Nakshatra number (period=27)
        sin_nak, cos_nak = encode_cyclic(df[f"{p}_nakshatra_num"].astype(float), period=27.0)
        df[f"{p}_nakshatra_num_sin"] = sin_nak.values
        df[f"{p}_nakshatra_num_cos"] = cos_nak.values
        cols_to_drop.append(f"{p}_nakshatra_num")

        # Sign text column — drop
        cols_to_drop.append(f"{p}_sign")

        # Retro — cast bool to int
        df[f"{p}_retro"] = df[f"{p}_retro"].astype(int)

        # NOTE: {p}_nakshatra string columns are intentionally NOT dropped here.
        # apply_nakshatra_encoding() (called in Plan 05) reads those columns.

    # Convert aspect bool columns to int (0/1)
    # Aspect columns follow pattern: {p1}_{p2}_{aspect_type}
    for col in df.columns:
        if col.endswith(tuple(_ASPECT_TYPES)):
            df[col] = df[col].astype(int)

    # Drop raw columns
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

    return df


# ---------------------------------------------------------------------------
# Nakshatra encoder
# ---------------------------------------------------------------------------


def fit_nakshatra_encoder(pre2000_df: pd.DataFrame):
    """Fit a OneHotEncoder on nakshatra columns using only pre-2000 training data.

    Encoder is fit on the closed vocabulary of 27 nakshatras seen in training data.
    At transform time, unknown categories (post-2000 data) produce a zero vector
    (handle_unknown='ignore').

    Args:
        pre2000_df: Ephemeris DataFrame restricted to dates before 2000-01-01.
                    Must contain {p}_nakshatra string columns for all planets.

    Returns:
        Fitted sklearn OneHotEncoder instance.
    """
    from sklearn.preprocessing import OneHotEncoder

    # sklearn < 1.0 uses `sparse=False`; sklearn >= 1.0 uses `sparse_output=False`
    import sklearn
    _sparse_kwarg = (
        {"sparse_output": False}
        if tuple(int(x) for x in sklearn.__version__.split(".")[:2]) >= (1, 0)
        else {"sparse": False}
    )
    encoder = OneHotEncoder(
        handle_unknown="ignore",
        dtype=np.uint8,
        **_sparse_kwarg,
    )
    encoder.fit(pre2000_df[NAKSHATRA_COLS])
    return encoder


def apply_nakshatra_encoding(df: pd.DataFrame, encoder) -> pd.DataFrame:
    """Apply fitted nakshatra one-hot encoding to the DataFrame.

    Transforms the 13 nakshatra name string columns into 351 uint8 one-hot columns
    and drops the original string columns.

    Args:
        df: DataFrame that still contains {p}_nakshatra string columns
            (i.e., the output of encode_ephemeris before this step).
        encoder: Fitted sklearn OneHotEncoder from fit_nakshatra_encoder().

    Returns:
        DataFrame with 351 nakshatra one-hot columns added and original
        nakshatra string columns removed.
    """
    ohe_array = encoder.transform(df[NAKSHATRA_COLS])
    # sklearn < 1.0 uses get_feature_names(); sklearn >= 1.0 uses get_feature_names_out()
    if hasattr(encoder, "get_feature_names_out"):
        ohe_col_names = encoder.get_feature_names_out(NAKSHATRA_COLS)
    else:
        ohe_col_names = encoder.get_feature_names(NAKSHATRA_COLS)
    ohe_df = pd.DataFrame(ohe_array, columns=ohe_col_names, index=df.index)

    result = df.drop(columns=NAKSHATRA_COLS)
    result = pd.concat([result, ohe_df], axis=1)
    return result


def save_encoder(encoder, path: str) -> None:
    """Persist a fitted encoder to disk using joblib.

    Args:
        encoder: Fitted sklearn encoder (e.g. OneHotEncoder from fit_nakshatra_encoder).
        path: File path to write (e.g. 'data/processed/nakshatra_encoder.pkl').
    """
    import joblib
    joblib.dump(encoder, path)
    logger.info(f"Encoder saved to {path}")


def load_encoder(path: str):
    """Load a fitted encoder from disk.

    Args:
        path: File path to read (e.g. 'data/processed/nakshatra_encoder.pkl').

    Returns:
        The deserialized encoder object.
    """
    import joblib
    return joblib.load(path)


# ---------------------------------------------------------------------------
# Temporal leakage guard
# ---------------------------------------------------------------------------


def assert_no_temporal_leakage(train_dates, test_dates) -> None:
    """Assert that training data is strictly before 2000-01-01 and test data is >= 2000-01-01.

    The 2000-01-01 split date is the hard temporal boundary for this project:
    train on 1900-1999, test on 2000-2026.

    Args:
        train_dates: Iterable of dates (datetime.date, pd.Timestamp, or str) in the training split.
        test_dates: Iterable of dates in the test split.

    Raises:
        AssertionError: If max(train_dates) >= 2000-01-01 (training data leaks into test era).
        AssertionError: If min(test_dates) < 2000-01-01 (test data contains pre-2000 rows).
    """
    from datetime import date as date_type

    SPLIT = date_type(2000, 1, 1)
    max_train = pd.to_datetime(pd.Series(list(train_dates))).max().date()
    min_test = pd.to_datetime(pd.Series(list(test_dates))).min().date()

    assert max_train < SPLIT, (
        f"Temporal leakage: training set contains rows on/after 2000-01-01. "
        f"max(train.date) = {max_train}"
    )
    assert min_test >= SPLIT, (
        f"Temporal leakage: test set contains rows before 2000-01-01 (pre-train era). "
        f"min(test.date) = {min_test}"
    )


# ---------------------------------------------------------------------------
# Negative downsampling
# ---------------------------------------------------------------------------


def downsample_negatives(
    df: pd.DataFrame, ratio: int = 10, random_state: int = 42
) -> pd.DataFrame:
    """Downsample negative (EQIndicator=0) rows to achieve target positive:negative ratio.

    All positive rows are preserved. Negatives are randomly sampled without replacement
    to yield min(ratio * n_positives, n_negatives) negative rows.

    The caller must ensure df is restricted to the pre-2000 training pool before calling.
    This function does not enforce the temporal boundary itself.

    Args:
        df: DataFrame with 'EQIndicator' column (1=positive, 0=negative).
        ratio: Target number of negatives per positive (e.g. 10 → 10:1). Default 10.
        random_state: Random seed for reproducibility. Default 42.

    Returns:
        DataFrame with all positives and downsampled negatives, reset index.
        Total rows = n_positives + min(ratio * n_positives, n_negatives).

    Raises:
        ValueError: If df does not contain an 'EQIndicator' column.
    """
    if "EQIndicator" not in df.columns:
        raise ValueError(
            "DataFrame must contain an 'EQIndicator' column (1=positive, 0=negative)."
        )

    positives = df[df["EQIndicator"] == 1]
    negatives = df[df["EQIndicator"] == 0]

    n_sample = min(ratio * len(positives), len(negatives))
    negatives_sampled = negatives.sample(n=n_sample, random_state=random_state)

    return pd.concat([positives, negatives_sampled]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Matrix chunk builder
# ---------------------------------------------------------------------------


def active_cells_list(active_cells_set: set) -> list[tuple[int, int]]:
    """Convert an active-cells set to a sorted list for deterministic iteration.

    Args:
        active_cells_set: Set of (grid_lat, grid_lon) tuples.

    Returns:
        List of (grid_lat, grid_lon) tuples sorted by (grid_lat, grid_lon).
    """
    return sorted(active_cells_set)


def build_matrix_chunk(
    ephe_row: pd.Series,
    active_cells: list[tuple[int, int]],
    eq_index: pd.Series,
    country_map: dict,
) -> pd.DataFrame:
    """Build one chunk of the training/test matrix for a single ephemeris date.

    Broadcasts the encoded ephemeris row to all active grid cells, then assigns
    EQIndicator=1 for cells that had a qualifying earthquake on that date.

    The ephemeris DataFrame must be date-indexed before iterating: callers should
    run ``ephe_df = ephe_df.set_index('date')`` so that ``ephe_row.name`` is the date.

    Args:
        ephe_row: One row from an encoded ephemeris DataFrame (pd.Series).
                  Row name (index) must be the date (str or Timestamp).
        active_cells: List of (grid_lat, grid_lon) int tuples.
        eq_index: pd.Series from build_eq_index — MultiIndex (date, grid_lat, grid_lon),
                  value 1 for cells with a qualifying earthquake on that date.
        country_map: Dict mapping (grid_lat, grid_lon) → country name string.

    Returns:
        DataFrame with len(active_cells) rows, columns from ephe_row plus:
        grid_lat (int), grid_lon (int), country (str), EQIndicator (int 0/1), date.
        Rows are sorted by (grid_lat, grid_lon).
    """
    n = len(active_cells)

    # Normalize row date to datetime.date for consistent eq_index lookup
    # (ephe_row.name may be a str, pd.Timestamp, or datetime.date depending on caller)
    from datetime import date as date_type
    raw_name = ephe_row.name
    if isinstance(raw_name, date_type):
        row_date = raw_name
    else:
        row_date = pd.Timestamp(raw_name).date()

    # Broadcast: repeat the encoded ephemeris row n times (exclude date if present as col)
    data = {col: [ephe_row[col]] * n for col in ephe_row.index if col != "date"}
    df = pd.DataFrame(data)

    cell_arr = np.array(active_cells)
    df["grid_lat"] = cell_arr[:, 0].astype(int)
    df["grid_lon"] = cell_arr[:, 1].astype(int)
    df["country"] = [country_map.get((r, c), "Unknown") for r, c in active_cells]
    df["date"] = row_date

    # Assign EQIndicator: 1 if (date, grid_lat, grid_lon) in eq_index, else 0
    idx = pd.MultiIndex.from_arrays(
        [
            pd.Index([row_date] * n, dtype=object),
            df["grid_lat"].values,
            df["grid_lon"].values,
        ]
    )
    df["EQIndicator"] = eq_index.reindex(idx).fillna(0).astype(int).values

    return df.sort_values(["grid_lat", "grid_lon"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Vectorized year-chunk builder (performance-critical path for main())
# ---------------------------------------------------------------------------


def build_matrix_year(
    year_ephe: pd.DataFrame,
    active_cells: list[tuple[int, int]],
    eq_index: pd.Series,
    country_map: dict,
) -> pd.DataFrame:
    """Build the feature matrix for all dates in a single year using vectorized ops.

    This is functionally equivalent to calling build_matrix_chunk for each row in
    year_ephe and concatenating, but avoids the Python row-by-row loop overhead
    by using numpy repeat/tile broadcasting.

    Args:
        year_ephe: Encoded ephemeris DataFrame for a single year (date-indexed).
        active_cells: Sorted list of (grid_lat, grid_lon) tuples.
        eq_index: MultiIndex Series from build_eq_index.
        country_map: Dict mapping (grid_lat, grid_lon) → country string.

    Returns:
        DataFrame with (len(year_ephe) * len(active_cells)) rows.
    """
    from datetime import date as date_type

    n_dates = len(year_ephe)
    n_cells = len(active_cells)

    # Convert date index to datetime.date objects
    dates_raw = year_ephe.index
    dates = [
        d if isinstance(d, date_type) else pd.Timestamp(d).date()
        for d in dates_raw
    ]

    # Precompute cell arrays
    cell_arr = np.array(active_cells, dtype=np.int32)
    grid_lats_tile = np.tile(cell_arr[:, 0], n_dates)
    grid_lons_tile = np.tile(cell_arr[:, 1], n_dates)
    countries_tile = [country_map.get((r, c), "Unknown") for r, c in active_cells] * n_dates
    dates_repeat = np.repeat(dates, n_cells)

    # Broadcast feature columns: repeat each date row n_cells times
    feat_cols = [c for c in year_ephe.columns if c != "date"]
    feature_vals = np.repeat(year_ephe[feat_cols].values, n_cells, axis=0)

    df = pd.DataFrame(feature_vals, columns=feat_cols)
    df["grid_lat"] = grid_lats_tile
    df["grid_lon"] = grid_lons_tile
    df["country"] = countries_tile
    df["date"] = dates_repeat

    # Build lookup MultiIndex for EQIndicator assignment
    idx = pd.MultiIndex.from_arrays(
        [
            pd.Index(list(dates_repeat), dtype=object),
            grid_lats_tile,
            grid_lons_tile,
        ]
    )
    df["EQIndicator"] = eq_index.reindex(idx).fillna(0).astype(int).values

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main orchestration pipeline
# ---------------------------------------------------------------------------


def main() -> None:
    """Orchestrate the full feature engineering pipeline.

    Reads raw ephemeris and USGS earthquake data, encodes all features,
    and writes four output artifacts to data/processed/:
        - feature_matrix_train.parquet  (~263K rows, pre-2000, 10:1 downsampled)
        - feature_matrix_test.parquet   (~8.5M rows, post-2000, NOT downsampled)
        - feature_columns.json          (ordered list of feature column names)
        - nakshatra_encoder.pkl         (fitted OneHotEncoder, fit on pre-2000 only)
    """
    import json
    from pathlib import Path

    import pyarrow as pa
    import pyarrow.parquet as pq
    from tqdm import tqdm

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    # -----------------------------------------------------------------------
    # Step 1: Load raw data
    # -----------------------------------------------------------------------
    logger.info("Loading raw data...")
    ephe_df = pd.read_csv("data/raw/ephemeris.csv", parse_dates=["date"])
    ephe_df = ephe_df.set_index("date")
    logger.info(f"Ephemeris loaded: {len(ephe_df):,} rows")

    usgs_df = pd.read_csv("data/raw/usgs_earthquakes.csv")
    logger.info(f"USGS loaded: {len(usgs_df):,} rows")

    # -----------------------------------------------------------------------
    # Step 2: Fit nakshatra encoder on pre-2000 data BEFORE encoding
    # -----------------------------------------------------------------------
    logger.info("Fitting nakshatra encoder on pre-2000 data...")
    pre2000_ephe_raw = ephe_df.loc[ephe_df.index < pd.Timestamp("2000-01-01")]
    encoder = fit_nakshatra_encoder(pre2000_ephe_raw)
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    save_encoder(encoder, "data/processed/nakshatra_encoder.pkl")
    logger.info(f"Pre-2000 rows for encoder fit: {len(pre2000_ephe_raw):,}")

    # -----------------------------------------------------------------------
    # Step 3: Encode full ephemeris (cyclic transforms, drop raw cols)
    # -----------------------------------------------------------------------
    logger.info("Encoding ephemeris (cyclic transforms)...")
    ephe_encoded = encode_ephemeris(ephe_df)
    logger.info(f"After encode_ephemeris: {ephe_encoded.shape[1]} columns")

    ephe_encoded = apply_nakshatra_encoding(ephe_encoded, encoder)
    logger.info(f"After apply_nakshatra_encoding: {ephe_encoded.shape[1]} columns")

    # -----------------------------------------------------------------------
    # Step 4: Build USGS lookup structures
    # -----------------------------------------------------------------------
    logger.info("Building USGS lookup structures...")
    active_cells = active_cells_list(build_active_cells(usgs_df))
    logger.info(f"Active cells: {len(active_cells)}")
    eq_index = build_eq_index(usgs_df)
    country_map = build_country_map(usgs_df)
    logger.info(f"EQ index size: {len(eq_index):,} entries")

    # -----------------------------------------------------------------------
    # Step 5: Build pre-2000 training matrix using vectorized year builder
    #
    # Memory note: The full pre-2000 matrix is ~210 GB (100 years × 329K rows × 813 cols).
    # We MUST downsample per-year before accumulating to keep peak RAM under ~3 GB.
    # Per-year downsampling preserves ALL positive rows; negatives are sampled 10:1.
    # -----------------------------------------------------------------------
    logger.info("Building pre-2000 training matrix (vectorized, per-year downsample)...")

    use_per_year_downsample = True
    pre2000_chunks = []

    for year in tqdm(range(1900, 2000), desc="Building pre-2000 chunks"):
        year_ephe = ephe_encoded[ephe_encoded.index.year == year]
        if len(year_ephe) == 0:
            continue
        year_df = build_matrix_year(year_ephe, active_cells, eq_index, country_map)
        year_df = downsample_negatives(year_df, ratio=10, random_state=42)
        pre2000_chunks.append(year_df)

    train_df = pd.concat(pre2000_chunks, ignore_index=True)
    del pre2000_chunks

    logger.info(
        f"Training set after per-year 10:1 downsample: {len(train_df):,} rows"
    )

    # -----------------------------------------------------------------------
    # Step 6: Assert temporal split
    # -----------------------------------------------------------------------
    assert train_df["date"].max() < pd.Timestamp("2000-01-01").date(), (
        f"Temporal leakage: training set max date = {train_df['date'].max()}"
    )
    logger.info("Temporal split assertion passed (max train date < 2000-01-01)")

    # -----------------------------------------------------------------------
    # Step 7: Write training parquet
    # -----------------------------------------------------------------------
    train_path = "data/processed/feature_matrix_train.parquet"
    train_df.to_parquet(train_path, engine="pyarrow", compression="snappy", index=False)
    logger.info(f"Wrote {train_path}")

    # -----------------------------------------------------------------------
    # Step 8: Build post-2000 test matrix in annual chunks, write incrementally
    # -----------------------------------------------------------------------
    logger.info("Building post-2000 test matrix (chunked by year, streaming write)...")
    test_path = Path("data/processed/feature_matrix_test.parquet")
    writer = None
    available_years = set(ephe_encoded.index.year.tolist())

    for year in tqdm(range(2000, 2027), desc="Building test set"):
        if year not in available_years:
            continue
        year_ephe = ephe_encoded[ephe_encoded.index.year == year]
        year_df = build_matrix_year(year_ephe, active_cells, eq_index, country_map)

        table = pa.Table.from_pandas(year_df, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(str(test_path), table.schema, compression="snappy")
        writer.write_table(table)
        del year_df

    if writer:
        writer.close()
    logger.info(f"Wrote {test_path}")

    # -----------------------------------------------------------------------
    # Step 9: Save feature_columns.json manifest
    # -----------------------------------------------------------------------
    meta_cols = {"EQIndicator", "grid_lat", "grid_lon", "country", "date"}
    feature_cols = [c for c in train_df.columns if c not in meta_cols]
    with open("data/processed/feature_columns.json", "w") as f:
        json.dump(feature_cols, f, indent=2)
    logger.info(f"Saved {len(feature_cols)} feature columns to feature_columns.json")

    # -----------------------------------------------------------------------
    # Step 10: Final validation assertions
    # -----------------------------------------------------------------------
    # Detect raw ephemeris columns: must end with the raw suffix but NOT be the grid cell columns
    # grid_lon is a meta column, not a raw ephemeris feature — exclude it from the check
    bad_cols = [
        c for c in train_df.columns
        if (c.endswith("_lon") and c not in ("grid_lon",))
        or c.endswith("_sign_num")
        or (c.endswith("_sign") and c not in ("grid_lon",))
        or c.endswith("_nakshatra_num")
    ]
    assert len(bad_cols) == 0, f"Raw columns found in output: {bad_cols}"
    assert "EQIndicator" in train_df.columns
    assert "grid_lat" in train_df.columns
    assert "grid_lon" in train_df.columns
    assert "country" in train_df.columns
    logger.info("All output assertions passed")


if __name__ == "__main__":
    main()
