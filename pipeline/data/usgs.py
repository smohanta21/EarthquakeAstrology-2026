"""
USGS FDSNWS Event API download script.

Downloads all M5.5+ earthquake records from 1900 through the current year,
paginating by 5-year chunks to stay safely under the 20,000-record API limit.
Saves a single deduplicated CSV to data/raw/usgs_earthquakes.csv.

Usage:
    python pipeline/data/usgs.py
    python pipeline/data/usgs.py --start-year 2000 --end-year 2010 --chunk-years 5
    python pipeline/data/usgs.py --output /path/to/output.csv

Exit code 0 on success, non-zero on failure.
"""

import argparse
import datetime
import io
import logging
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
MIN_MAG = 5.5
OUTPUT_PATH = Path("data/raw/usgs_earthquakes.csv")
TRUNCATION_LIMIT = 20_000

REQUIRED_COLUMNS = ["time", "latitude", "longitude", "depth", "mag", "place", "type"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def fetch_decade(start_year: int, end_year: int) -> pd.DataFrame:
    """
    Fetch M5.5+ earthquake records from the USGS FDSNWS API for a date range.

    Parameters
    ----------
    start_year : int
        First year of the range (inclusive).
    end_year : int
        Last year of the range (inclusive).

    Returns
    -------
    pd.DataFrame
        DataFrame of earthquake records with at least the required columns.

    Raises
    ------
    RuntimeError
        If the HTTP request fails after retries, or if the response contains
        exactly TRUNCATION_LIMIT rows (indicating silent data truncation).
    """
    params = {
        "format": "csv",
        "minmagnitude": MIN_MAG,
        "starttime": f"{start_year}-01-01",
        "endtime": f"{end_year}-12-31",
        "orderby": "time-asc",
    }

    max_retries = 3
    backoff_seconds = [2, 4, 8]

    last_error: Exception | None = None
    for attempt, wait in enumerate(backoff_seconds, start=1):
        try:
            response = requests.get(USGS_URL, params=params, timeout=60)
            if response.status_code != 200:
                raise RuntimeError(
                    f"USGS API returned HTTP {response.status_code} for "
                    f"{start_year}-{end_year}: {response.text[:200]}"
                )
            break
        except RuntimeError:
            raise  # Don't retry on explicit HTTP errors
        except requests.RequestException as exc:
            last_error = exc
            logger.warning(
                "Request failed (attempt %d/%d): %s. Retrying in %ds…",
                attempt,
                max_retries,
                exc,
                wait,
            )
            time.sleep(wait)
    else:
        raise RuntimeError(
            f"Failed to fetch {start_year}-{end_year} after {max_retries} attempts: {last_error}"
        )

    df = pd.read_csv(io.StringIO(response.text))

    # Truncation guard: USGS silently caps at 20,000 rows.
    if len(df) == TRUNCATION_LIMIT:
        msg = (
            f"Decade {start_year}-{end_year} hit the 20k limit "
            f"({TRUNCATION_LIMIT} rows returned) — sub-chunk required to avoid data loss."
        )
        logger.warning(msg)
        raise RuntimeError(msg)

    logger.info(
        "Fetched %d events for %d–%d", len(df), start_year, end_year
    )
    return df


def fetch_all(
    start_year: int = 1900,
    end_year: int | None = None,
    chunk_years: int = 5,
) -> pd.DataFrame:
    """
    Fetch all M5.5+ earthquakes across a year range by chunking into sub-periods.

    Parameters
    ----------
    start_year : int
        First year to include (default 1900).
    end_year : int or None
        Last year to include (default: current calendar year).
    chunk_years : int
        Number of years per API request (default 5).

    Returns
    -------
    pd.DataFrame
        Concatenated, deduplicated DataFrame of all events.
    """
    if end_year is None:
        end_year = datetime.datetime.now().year

    # Build list of (chunk_start, chunk_end) year pairs
    chunks: list[tuple[int, int]] = []
    year = start_year
    while year <= end_year:
        chunk_end = min(year + chunk_years - 1, end_year)
        chunks.append((year, chunk_end))
        year += chunk_years

    all_frames: list[pd.DataFrame] = []

    for chunk_start, chunk_end in tqdm(chunks, desc="Downloading USGS data", unit="chunk"):
        df = fetch_decade(chunk_start, chunk_end)
        all_frames.append(df)
        time.sleep(0.5)  # Be respectful of the public API

    if not all_frames:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    combined = pd.concat(all_frames, ignore_index=True)

    # Deduplicate on USGS event id (chunk boundaries may produce duplicates)
    if "id" in combined.columns:
        combined = combined.drop_duplicates(subset=["id"], keep="first")

    return combined


def validate_result(df: pd.DataFrame) -> bool:
    """
    Validate the combined earthquake DataFrame before writing to disk.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame returned by fetch_all.

    Returns
    -------
    bool
        True if all hard checks pass.

    Raises
    ------
    AssertionError
        If required columns are missing or minimum magnitude is below MIN_MAG.
    """
    # Hard check 1: required columns
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    assert not missing, f"Required columns missing from DataFrame: {missing}"

    # Hard check 2: no events below the magnitude filter
    assert df["mag"].min() >= MIN_MAG, (
        f"DataFrame contains events with mag < {MIN_MAG}: "
        f"min observed = {df['mag'].min()}"
    )

    # Soft check: row count sanity
    if len(df) <= 50_000:
        logger.warning(
            "Total event count is %d, which is below the expected 50,000+ for a "
            "1900–present M5.5+ catalog. Check for download errors or sparse early years.",
            len(df),
        )

    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for the USGS download script."""
    parser = argparse.ArgumentParser(
        description="Download M5.5+ earthquake catalog from USGS FDSNWS Event API."
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=1900,
        help="First year to include (default: 1900)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=datetime.datetime.now().year,
        help="Last year to include (default: current year)",
    )
    parser.add_argument(
        "--chunk-years",
        type=int,
        default=5,
        help="Years per API request chunk (default: 5)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help=f"Output CSV path (default: {OUTPUT_PATH})",
    )
    args = parser.parse_args()

    logger.info(
        "Starting USGS download: %d–%d in %d-year chunks → %s",
        args.start_year,
        args.end_year,
        args.chunk_years,
        args.output,
    )

    try:
        df = fetch_all(
            start_year=args.start_year,
            end_year=args.end_year,
            chunk_years=args.chunk_years,
        )
    except RuntimeError as exc:
        logger.error("Download failed: %s", exc)
        sys.exit(1)

    try:
        validate_result(df)
    except AssertionError as exc:
        logger.error("Validation failed: %s", exc)
        sys.exit(1)

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)

    print(f"Downloaded {len(df):,} events. Saved to {args.output}")


if __name__ == "__main__":
    main()
