# Earthquake Astrology Prediction 2026

## What This Is

A machine learning system that combines astrological planetary position data with historical earthquake records (M5.5+) to predict earthquake dates and geographic regions. The system trains on 1900–2000 historical data, validates on 2000–2026, and produces predictions for the remainder of 2026. A Next.js web application displays predictions as an interactive calendar view, deployed to Vercel.

## Core Value

Accurate prediction of high-risk earthquake dates and regions for 2026 using astrological planetary patterns — trained on 100 years of data, validated on 26 years of out-of-sample events.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Earthquake data pipeline: Auto-download USGS Catalog API data for M5.5+ events from 1900–2026
- [ ] Astrological data pipeline: Automate planetary position data collection (scraping Astro Seek or Swiss Ephemeris) for 1900–2026
- [ ] Feature engineering: Compute planetary degrees, retrograde status, aspects, signs, houses, and nakshatras matching existing code patterns
- [ ] ML model: Train on 1900–2000 earthquake data, evaluate on 2000–2026 held-out test set
- [ ] Regional prediction: Model outputs predicted date + country + lat/long grid cell for high-risk events
- [ ] 2026 predictions: Generate predictions for March–December 2026 and export as JSON
- [ ] Web UI: Next.js calendar view showing high-risk earthquake dates for 2026 with country/region info
- [ ] Vercel deployment: Static pre-computed predictions served via Next.js app on Vercel

### Out of Scope

- Real-time / live model inference on web requests — pre-computed predictions only
- Magnitude prediction — binary risk classification only (earthquake yes/no per date/region)
- Mobile app — web-first
- Jupyter notebooks — migrating to clean Python scripts

## Context

The existing codebase (in the project root and Archive/) contains Jupyter notebooks with the original ML pipeline:
- Data: pre-processed CSV files combining USGS earthquake records with astrological position data
- Features: ~265–309 columns covering planetary degrees, retrograde flags, aspect tables, zodiac signs, house positions, nakshatras (Vedic stars)
- Models tested: Logistic Regression (L1/L2/ElasticNet), KNN — best performers were Lasso LogReg (~73% accuracy) and KNN with distance weighting
- Training data covered ~1901–2011, tested on 2011–2020
- The new project extends this to a clean 1900–2000 train / 2000–2026 test split

Key astrological features used in existing code:
- Planetary degrees (Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Node, Lilith, Chiron, Pluto, Uranus, Neptune)
- Retrograde status, zodiac signs, house placements (harmonic houses: HA:2, HA:3, HA:6, HA:7, HA:8, HA:9)
- Planetary aspects (conjunctions, oppositions, etc.), Nakshatra (Vedic star) of key planets

## Constraints

- **Data**: Astrological data must be recomputed from Astro Seek or Swiss Ephemeris — existing CSVs cover only through ~2020
- **Deployment**: Web app must deploy to Vercel — Python ML must run offline; only static JSON predictions go to the web
- **Magnitude filter**: Only include M5.5+ earthquakes as positive EQ events
- **Code format**: Python scripts (.py), not Jupyter notebooks
- **Stack**: Next.js + React for web UI

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Train on 1900–2000, test on 2000–2026 | Clean temporal holdout — no data leakage, ~26 years of out-of-sample validation | — Pending |
| Pre-computed predictions on Vercel | Python ML can't run on Vercel serverless; keeps deployment simple and fast | — Pending |
| USGS API for earthquake data | Official, free, covers full 1900–2026 range consistently | — Pending |
| Swiss Ephemeris / Astro Seek scraping for planetary data | Existing data only covers ~1901–2020; need to extend to 2026 | — Pending |
| Next.js + React for web UI | Best Vercel integration, full-stack, can serve predictions as static JSON | — Pending |

---
*Last updated: 2026-03-14 after initialization*
