import unittest

from scripts.export_external_discovery_review import review_rows


def profile(org: str, evidence=None) -> dict:
    return {"organisation_number": org, "name": f"Company {org}", "evidence": evidence or {}}


class ExternalDiscoveryReviewExportTests(unittest.TestCase):
    def test_exports_pending_review_and_does_not_copy_raw_search_text(self):
        rows = [profile("123456789", {
            "website_discovery": {
                "status": "available",
                "value": {
                    "candidate_count": 3,
                    "selected_for_independent_crawl": True,
                    "provider_status": 200,
                    "raw_title": "Do not retain this title",
                    "raw_snippet": "Do not retain this snippet",
                },
            },
            "website_discovered": {
                "status": "available",
                "source_type": "search_discovered_company_website",
                "source_url": "https://company.example/",
                "retrieved_at": "2026-10-13T10:00:00Z",
                "content_sha256": "abc123",
                "value": {"publishable": False, "identity_gate_reason": "insufficient_identity_evidence"},
            },
        })]
        result = review_rows(rows)[0]
        self.assertEqual(result["organisation_number"], "123456789")
        self.assertEqual(result["candidate_url"], "https://company.example/")
        self.assertEqual(result["reviewer_decision"], "pending")
        self.assertIsNone(result["exact_entity"])
        self.assertEqual(result["search_candidate_count"], 3)
        self.assertFalse(result["raw_search_results_persisted"])
        self.assertNotIn("raw_title", result)
        self.assertNotIn("raw_snippet", result)

    def test_preserves_abstention_for_recall_review(self):
        result = review_rows([profile("123456789")])[0]
        self.assertEqual(result["crawl_status"], "no_candidate_crawled")
        self.assertIsNone(result["candidate_url"])
        self.assertEqual(result["reviewer_decision"], "pending")

    def test_duplicate_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            review_rows([profile("123456789"), profile("123456789")])

    def test_invalid_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "digit-only"):
            review_rows([profile("not-a-number")])


if __name__ == "__main__":
    unittest.main()
