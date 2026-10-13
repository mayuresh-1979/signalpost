import unittest

from scripts.prepare_external_discovery_benchmark import prepare_split


def profile(org: str, website: str = "") -> dict:
    return {"organisation_number": org, "name": f"Company {org}", "website": website}


class ExternalDiscoveryBenchmarkSplitTests(unittest.TestCase):
    def test_split_is_deterministic_and_disjoint(self):
        rows = [profile(f"{i:09d}") for i in range(1, 21)]
        dev1, val1, manifest1 = prepare_split(rows, 5)
        dev2, val2, manifest2 = prepare_split(list(reversed(rows)), 5)
        dev_ids = {row["organisation_number"] for row in dev1}
        val_ids = {row["organisation_number"] for row in val1}
        self.assertEqual(dev_ids, {row["organisation_number"] for row in dev2})
        self.assertEqual(val_ids, {row["organisation_number"] for row in val2})
        self.assertEqual(dev_ids & val_ids, set())
        self.assertEqual(manifest1["development_validation_overlap"], 0)
        self.assertEqual(manifest1["network_requests_made"], 0)
        self.assertEqual(manifest1, manifest2)

    def test_profiles_with_websites_are_excluded(self):
        rows = [profile(f"{i:09d}", "https://example.no") for i in range(1, 4)]
        rows += [profile(f"{i:09d}") for i in range(4, 14)]
        dev, val, manifest = prepare_split(rows, 5)
        all_ids = {row["organisation_number"] for row in dev + val}
        self.assertTrue(all(int(org) >= 4 for org in all_ids))
        self.assertEqual(manifest["profiles_without_registry_website"], 10)

    def test_duplicate_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            prepare_split([profile("123456789"), profile("123456789")], 1)

    def test_insufficient_candidates_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "need at least"):
            prepare_split([profile("123456789")], 1)

    def test_invalid_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "digits only"):
            prepare_split([profile("abc")], 1)


if __name__ == "__main__":
    unittest.main()
