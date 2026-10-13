import unittest
from datetime import datetime, timezone

from scripts.evaluate_external_footprint import is_fresh


class ExternalFootprintFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.as_of = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)

    def test_observation_inside_window_is_fresh(self):
        self.assertTrue(is_fresh("2026-09-01", self.as_of))

    def test_observation_older_than_window_is_stale(self):
        self.assertFalse(is_fresh("2026-08-28", self.as_of))

    def test_future_dated_observation_is_not_fresh(self):
        self.assertFalse(is_fresh("2026-10-14", self.as_of))

    def test_missing_or_invalid_effective_date_is_not_fresh(self):
        self.assertFalse(is_fresh(None, self.as_of))
        self.assertFalse(is_fresh("not-a-date", self.as_of))

    def test_naive_evaluation_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            is_fresh("2026-10-10", datetime(2026, 10, 13, 12, 0))


if __name__ == "__main__":
    unittest.main()
