from __future__ import annotations

import unittest

from scripts.run_no_api_domain_discovery import guessed_domains, has_known_website


class NoApiDomainDiscoveryTests(unittest.TestCase):
    def test_domains_are_deterministic_and_bounded(self) -> None:
        self.assertEqual(
            guessed_domains("Nordlys Teknologi AS"),
            ["nordlysteknologi.no", "nordlys-teknologi.no", "nordlysteknologi.com"],
        )
        self.assertEqual(len(guessed_domains("Nordlys Teknologi AS")), 3)

    def test_legal_suffix_is_removed_but_name_is_preserved(self) -> None:
        self.assertEqual(guessed_domains("Ålesund Data ASA")[0], "alesunddata.no")

    def test_empty_or_suffix_only_names_do_not_create_domains(self) -> None:
        self.assertEqual(guessed_domains("AS"), [])
        self.assertEqual(guessed_domains("   "), [])

    def test_known_website_is_skipped(self) -> None:
        self.assertTrue(has_known_website({"website": "https://example.no"}))
        self.assertTrue(has_known_website({
            "evidence": {"website": {"status": "available", "source_url": "https://example.no"}}
        }))

    def test_unverified_or_missing_website_is_not_treated_as_known(self) -> None:
        self.assertFalse(has_known_website({}))
        self.assertFalse(has_known_website({
            "evidence": {"website": {"status": "not_found", "source_url": "https://example.no"}}
        }))


if __name__ == "__main__":
    unittest.main()
