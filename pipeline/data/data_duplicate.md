# Data Extraction

This module handles the extraction and processing of earthquake and ephemeris data for the EarthquakeAstrology pipeline.

## Overview

The data extraction pipeline ingests raw data from multiple sources and prepares it for feature engineering and model training. This includes earthquake data from USGS and astronomical ephemeris data for astrological calculations.

## Components

### USGS Earthquake Data (`usgs.py`)
- Extracts earthquake data from USGS sources
- Handles data cleaning and validation
- Standardizes earthquake metrics (magnitude, location, depth, time)

### Ephemeris Data (`ephemeris.py`)
- Retrieves or loads astronomical ephemeris data
- Manages planetary position calculations
- Provides ephemeris data for astrological feature extraction

### Ephemeris Validation (`validate_ephemeris.py`)
- Validates ephemeris data integrity
- Ensures data consistency and completeness
- Provides quality assurance checks for astronomical calculations

## Data Flow

1. **Raw Data Input**: Earthquake data from USGS API/files and ephemeris files
2. **Extraction**: Parse and standardize data format
3. **Validation**: Check data quality and completeness
4. **Output**: Cleaned data ready for feature engineering

## Usage

```python
from pipeline.data.usgs import extract_usgs_data
from pipeline.data.ephemeris import load_ephemeris
from pipeline.data.validate_ephemeris import validate_ephemeris

# Extract USGS earthquake data
earthquake_data = extract_usgs_data()

# Load ephemeris data
ephemeris_data = load_ephemeris()

# Validate data
validate_ephemeris(ephemeris_data)
```

## Input Formats

### USGS Data
- CSV format with earthquake events
- Required fields: timestamp, latitude, longitude, magnitude, depth

### Ephemeris Data
- Swiss Ephemeris format (.se1 files)
- Text-based ephemeris files for planetary calculations

## Output

Processed data is output to `data/processed/` directory in standardized formats ready for feature engineering.

## Configuration

Data sources and parameters can be configured through the main pipeline configuration files.

## Testing

Unit tests for data extraction are available in `tests/test_usgs.py`, `tests/test_ephemeris.py`, and `tests/test_validate_ephemeris.py`.
