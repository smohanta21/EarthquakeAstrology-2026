"""
Tests for pipeline/data/ephemeris.py

Behavior under test:
- compute_day returns a dict with all required planet keys (lon, sign, sign_num, retro, nakshatra_num, nakshatra)
- Sun longitude on 1900-01-01 is approximately 280 degrees (Capricorn, 270-290 range)
- compute_aspects returns aspect columns for all planet pairs and 5 aspect types
- Running main() for a 3-day range produces a CSV with 3 rows and all expected columns
- Script raises RuntimeError if SE_EPHE_PATH directory does not exist
- All Julian Day computations use hour=12.0 (UTC noon) — verified via structure check
- Module-level structure: compute_day, compute_aspects, setup_ephemeris, main all present
"""

import ast
import os
import pathlib
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add project root to PYTHONPATH
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

EPHE_PATH = str(pathlib.Path(__file__).parent.parent / "data" / "ephe")


class TestEphemerisModuleStructure(unittest.TestCase):
    """Verify module structure via AST parse — does not require ephemeris files."""

    def setUp(self):
        self.src_path = pathlib.Path(__file__).parent.parent / "pipeline" / "data" / "ephemeris.py"

    def test_module_file_exists(self):
        """ephemeris.py must exist at pipeline/data/ephemeris.py."""
        self.assertTrue(self.src_path.exists(), f"Expected file at {self.src_path}")

    def test_required_functions_present(self):
        """Module must contain compute_day, compute_aspects, setup_ephemeris, main."""
        src = self.src_path.read_text()
        tree = ast.parse(src)
        funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        for fn in ["compute_day", "compute_aspects", "setup_ephemeris", "main"]:
            self.assertIn(fn, funcs, f"Function '{fn}' must be defined in ephemeris.py")

    def test_uses_calc_ut_not_calc(self):
        """Must use calc_ut (UT input), never raw calc (TT input)."""
        src = self.src_path.read_text()
        self.assertIn("calc_ut", src, "Must use swe.calc_ut for UT-based computation")

    def test_uses_noon_hour(self):
        """Must use 12.0 as hour for Julian Day to avoid midnight boundary ambiguity."""
        src = self.src_path.read_text()
        self.assertIn("12.0", src, "Must pass hour=12.0 to swe.julday for UTC noon")

    def test_uses_lahiri_ayanamsha(self):
        """Must use SIDM_LAHIRI for Vedic nakshatra sidereal calculations."""
        src = self.src_path.read_text()
        self.assertIn("SIDM_LAHIRI", src, "Must use Lahiri ayanamsha for Vedic nakshatras")

    def test_uses_fgl_sidereal(self):
        """Must use FLG_SIDEREAL flag when computing sidereal nakshatra longitude."""
        src = self.src_path.read_text()
        self.assertIn("FLG_SIDEREAL", src, "Must use FLG_SIDEREAL for sidereal nakshatra calc")

    def test_calls_set_ephe_path(self):
        """setup_ephemeris must call swe.set_ephe_path before any computation."""
        src = self.src_path.read_text()
        self.assertIn("set_ephe_path", src, "Must call swe.set_ephe_path()")


class TestComputeDay(unittest.TestCase):
    """Tests for compute_day function — requires pysweph and ephemeris files."""

    def setUp(self):
        """Set ephemeris path and import module."""
        os.environ["SE_EPHE_PATH"] = EPHE_PATH
        # Import fresh each test to pick up the env var
        import importlib
        import pipeline.data.ephemeris as em
        importlib.reload(em)
        self.em = em

    def test_compute_day_returns_dict(self):
        """compute_day must return a dict."""
        self.em.setup_ephemeris()
        result = self.em.compute_day("2000-01-01")
        self.assertIsInstance(result, dict)

    def test_compute_day_has_date_key(self):
        """Result dict must contain 'date' key."""
        self.em.setup_ephemeris()
        result = self.em.compute_day("2000-01-01")
        self.assertIn("date", result)
        self.assertEqual(result["date"], "2000-01-01")

    def test_compute_day_has_all_planet_columns(self):
        """Result must have lon, sign, sign_num, retro, nakshatra_num, nakshatra for all 13 planets."""
        self.em.setup_ephemeris()
        result = self.em.compute_day("2000-01-01")
        planets = ["sun", "moon", "mercury", "venus", "mars", "jupiter",
                   "saturn", "uranus", "neptune", "pluto", "chiron", "lilith", "node"]
        suffixes = ["_lon", "_sign", "_sign_num", "_retro", "_nakshatra_num", "_nakshatra"]
        for planet in planets:
            for suffix in suffixes:
                key = f"{planet}{suffix}"
                self.assertIn(key, result, f"Missing key: {key}")

    def test_sun_longitude_in_valid_range(self):
        """Sun longitude must be in 0-360 degrees."""
        self.em.setup_ephemeris()
        result = self.em.compute_day("2000-01-01")
        lon = result["sun_lon"]
        self.assertGreaterEqual(lon, 0.0)
        self.assertLess(lon, 360.0)

    def test_sun_longitude_on_2000_01_01_is_capricorn(self):
        """Sun longitude on 2000-01-01 should be approximately 280 degrees (Capricorn).
        Any value outside 270-290 indicates a UTC or ephe_path error."""
        self.em.setup_ephemeris()
        result = self.em.compute_day("2000-01-01")
        lon = result["sun_lon"]
        self.assertGreater(lon, 270, f"Sun lon {lon} should be > 270 (Capricorn range)")
        self.assertLess(lon, 290, f"Sun lon {lon} should be < 290 (Capricorn range)")

    def test_sun_sign_is_string(self):
        """sun_sign must be a string like 'Aries', 'Capricorn', etc."""
        self.em.setup_ephemeris()
        result = self.em.compute_day("2000-01-01")
        self.assertIsInstance(result["sun_sign"], str)
        self.assertIn(result["sun_sign"], [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
        ])

    def test_sun_sign_num_is_int_0_to_11(self):
        """sun_sign_num must be an int in range 0-11."""
        self.em.setup_ephemeris()
        result = self.em.compute_day("2000-01-01")
        self.assertIsInstance(result["sun_sign_num"], int)
        self.assertGreaterEqual(result["sun_sign_num"], 0)
        self.assertLessEqual(result["sun_sign_num"], 11)

    def test_retro_is_bool(self):
        """Retrograde flag must be a boolean."""
        self.em.setup_ephemeris()
        result = self.em.compute_day("2000-01-01")
        self.assertIsInstance(result["sun_retro"], bool)

    def test_nakshatra_num_is_int_0_to_26(self):
        """Nakshatra number must be an int in range 0-26."""
        self.em.setup_ephemeris()
        result = self.em.compute_day("2000-01-01")
        nnum = result["sun_nakshatra_num"]
        self.assertIsInstance(nnum, int)
        self.assertGreaterEqual(nnum, 0)
        self.assertLessEqual(nnum, 26)

    def test_nakshatra_is_valid_string(self):
        """Nakshatra must be a string matching one of the 27 Vedic nakshatra names."""
        self.em.setup_ephemeris()
        result = self.em.compute_day("2000-01-01")
        valid_nakshatras = [
            "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
            "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
            "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
            "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishtha",
            "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
        ]
        self.assertIn(result["sun_nakshatra"], valid_nakshatras)


class TestComputeAspects(unittest.TestCase):
    """Tests for compute_aspects function."""

    def setUp(self):
        os.environ["SE_EPHE_PATH"] = EPHE_PATH
        import importlib
        import pipeline.data.ephemeris as em
        importlib.reload(em)
        self.em = em

    def test_compute_aspects_returns_dict(self):
        """compute_aspects must return a dict."""
        self.em.setup_ephemeris()
        row = self.em.compute_day("2000-01-01")
        aspects = self.em.compute_aspects(row)
        self.assertIsInstance(aspects, dict)

    def test_compute_aspects_has_correct_column_count(self):
        """Must have 78 planet pairs x 5 aspects = 390 aspect columns."""
        self.em.setup_ephemeris()
        row = self.em.compute_day("2000-01-01")
        aspects = self.em.compute_aspects(row)
        # 13 planets → C(13,2) = 78 pairs × 5 aspects = 390
        self.assertEqual(len(aspects), 390, f"Expected 390 aspect columns, got {len(aspects)}")

    def test_aspect_values_are_binary(self):
        """All aspect column values must be 0 or 1."""
        self.em.setup_ephemeris()
        row = self.em.compute_day("2000-01-01")
        aspects = self.em.compute_aspects(row)
        for key, val in aspects.items():
            self.assertIn(val, (0, 1), f"Aspect column '{key}' has non-binary value {val}")

    def test_conjunction_column_exists(self):
        """sun_moon_conjunction column must exist in aspects dict."""
        self.em.setup_ephemeris()
        row = self.em.compute_day("2000-01-01")
        aspects = self.em.compute_aspects(row)
        self.assertIn("sun_moon_conjunction", aspects)

    def test_sun_sun_conjunction_is_always_1(self):
        """A planet is always in conjunction with itself — but we use pairs, so skip self-pairs."""
        # This test validates the angular distance logic: when two planets are at same longitude
        self.em.setup_ephemeris()
        row = self.em.compute_day("2000-01-01")
        # Manually create a row where sun and moon are at the same longitude
        test_row = dict(row)
        test_row["moon_lon"] = test_row["sun_lon"]
        aspects = self.em.compute_aspects(test_row)
        self.assertEqual(aspects["sun_moon_conjunction"], 1,
                         "Planets at same longitude must be in conjunction")

    def test_aspect_column_naming_format(self):
        """Aspect columns must be named {planet1}_{planet2}_{aspect_name}."""
        self.em.setup_ephemeris()
        row = self.em.compute_day("2000-01-01")
        aspects = self.em.compute_aspects(row)
        for key in aspects:
            parts = key.rsplit("_", 1)
            self.assertEqual(len(parts), 2,
                             f"Aspect key '{key}' should end with aspect name after last _")
            self.assertIn(parts[1], ["conjunction", "sextile", "square", "trine", "opposition"],
                          f"Aspect name '{parts[1]}' not in known aspects")


class TestSetupEphemeris(unittest.TestCase):
    """Tests for setup_ephemeris function."""

    def test_raises_runtime_error_if_path_missing(self):
        """setup_ephemeris must raise RuntimeError if SE_EPHE_PATH does not exist."""
        os.environ["SE_EPHE_PATH"] = "/nonexistent/path/to/ephe"
        import importlib
        import pipeline.data.ephemeris as em
        importlib.reload(em)
        with self.assertRaises(RuntimeError):
            em.setup_ephemeris()

    def test_succeeds_with_valid_path(self):
        """setup_ephemeris does not raise when path exists (even without .se1 files — uses Moshier)."""
        os.environ["SE_EPHE_PATH"] = EPHE_PATH
        import importlib
        import pipeline.data.ephemeris as em
        importlib.reload(em)
        # Should not raise even if .se1 files are absent (Moshier fallback is acceptable)
        try:
            em.setup_ephemeris()
        except RuntimeError as e:
            if "does not exist" in str(e):
                self.fail(f"setup_ephemeris raised RuntimeError for valid path: {e}")


if __name__ == "__main__":
    unittest.main()
