"""
Unit tests for Etkinliktoplama data pipeline.
Tests config, taxonomy, normalize, and registered scrapers.
"""

import unittest
from typing import Dict, Any

from pipeline.config import load_sources_config, now_iso, today_utc, get_output_dir
from pipeline.taxonomy import classify_event, is_valid_class, ISO_COUNTRIES
from pipeline.normalize import normalize_event
from pipeline.main import SCRAPER_MAP

class TestPipeline(unittest.TestCase):

    def test_config_functions(self):
        sources = load_sources_config()
        self.assertIsInstance(sources, list)
        self.assertGreater(len(sources), 0)

        timestamp = now_iso()
        self.assertIsInstance(timestamp, str)
        self.assertIn("T", timestamp)

        date_str = today_utc()
        self.assertIsInstance(date_str, str)
        self.assertEqual(len(date_str), 10)

        out_dir = get_output_dir()
        self.assertIsInstance(out_dir, str)

    def test_taxonomy_functions(self):
        category, sub_type = classify_event("Tarkan Konseri Harbiye", "Harbiye açık hava müzik gösterisi")
        self.assertEqual(category, "concert")

        valid = is_valid_class({"interest": "concert"})
        self.assertTrue(valid)

        invalid = is_valid_class({"interest": "unknown_category_xyz"})
        self.assertFalse(invalid)

        self.assertIn("TR", ISO_COUNTRIES)

    def test_normalize_event(self):
        raw = {
            "title": "İzmir Kamp ve Karavan Festivali",
            "start_date": "2025-06-01",
            "city": "İzmir",
            "venue": "Fuar İzmir"
        }
        norm = normalize_event(raw)
        self.assertIsNotNone(norm)
        self.assertEqual(norm["title"], "İzmir Kamp ve Karavan Festivali")
        self.assertEqual(norm["location"]["country_code"], "TR")
        self.assertEqual(norm["classification"]["interest"], "camping")

        # Invalid raw event without title
        invalid_raw = {"description": "Açıklama var ama başlık yok"}
        norm_invalid = normalize_event(invalid_raw)
        self.assertIsNone(norm_invalid)

    def test_registered_scrapers(self):
        self.assertIsInstance(SCRAPER_MAP, dict)
        self.assertIn("community", SCRAPER_MAP)
        self.assertIn("web_social", SCRAPER_MAP)

        for name, scraper_func in SCRAPER_MAP.items():
            try:
                res = scraper_func()
                self.assertIsInstance(res, list, f"Scraper '{name}' did not return a list.")
            except Exception as e:
                self.fail(f"Scraper '{name}' raised an unexpected exception: {e}")

if __name__ == "__main__":
    unittest.main()
