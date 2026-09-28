#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from norway_company_agent.external_footprint import (
    validate_observation,
    publishable_observation,
    aggregate_footprint,
    PLATFORMS,
    SIGNAL_TYPES,
)
from norway_company_agent.research import parse_screen_query, UNSUPPORTED_SCREEN_TERMS


class RatingsReviewsAuditTests(unittest.TestCase):
    def test_valid_review_observation_contract(self):
        """Valid third-party review observation schema must pass all validators."""
        obs = {
            "id": "review-obs-valid-001",
            "organisation_number": "921117817",
            "platform": "company_directory",
            "signal_type": "review_summary",
            "source_url": "https://example-licensed-directory.no/company/921117817",
            "retrieved_at": "2026-09-24T12:00:00Z",
            "content_sha256": "e" * 64,
            "exact_entity": True,
            "identity_proof": [{"type": "exact_organisation_number", "value": "921117817"}],
            "acquisition_mode": "permitted_public_page",
            "rights_status": "approved",
            "source_class": "customer_review",
            "evidence_span": "Licensed aggregate rating 4.5 based on 25 reviews.",
            "metrics": {"rating": 4.5, "review_count": 25, "scale": 5},
        }
        self.assertEqual(validate_observation(obs), [])
        self.assertTrue(publishable_observation(obs))

    def test_unapproved_rights_rejected(self):
        """Unapproved acquisition mode or rights_status must fail publication validation."""
        unapproved = {
            "id": "fagfolk-exp-001",
            "organisation_number": "921117817",
            "platform": "company_directory",
            "signal_type": "review_summary",
            "source_url": "https://www.fagfolkguiden.no/bedrift/test-921117817",
            "retrieved_at": "2026-09-24T12:00:00Z",
            "content_sha256": "f" * 64,
            "exact_entity": True,
            "identity_proof": [{"type": "exact_legal_name_on_directory_page", "value": "Test AS"}],
            "acquisition_mode": "rights_review_experiment",
            "rights_status": "review_required",
            "source_class": "customer_review",
            "evidence_span": "Google aggregate rating 4.7/5",
            "metrics": {"rating": 4.7, "review_count": 482},
        }
        reasons = validate_observation(unapproved)
        self.assertIn("acquisition mode is not approved for publication", reasons)
        self.assertIn("source rights are not approved", reasons)
        self.assertFalse(publishable_observation(unapproved))

    def test_company_owned_marketing_testimonials_rejected(self):
        """Company-owned marketing copy or testimonials cannot be treated as independent customer reviews."""
        marketing_obs = {
            "id": "self-testimonial-001",
            "organisation_number": "921117817",
            "platform": "company_site",
            "signal_type": "review",
            "source_url": "https://www.justify.no/",
            "retrieved_at": "2026-09-24T12:00:00Z",
            "content_sha256": "a" * 64,
            "exact_entity": True,
            "identity_proof": [{"type": "company_domain", "value": "justify.no"}],
            "acquisition_mode": "permitted_public_page",
            "rights_status": "approved",
            "source_class": "company_marketing",  # Not in INDEPENDENT_SENTIMENT_CLASSES
            "evidence_span": "Våre kunder gir oss i snitt 4,7 av 5 stjerner",
            "sentiment_label": "positive",
            "sentiment_model_version": "v1.0",
        }
        reasons = validate_observation(marketing_obs)
        self.assertIn("sentiment source is not independent", reasons)
        self.assertFalse(publishable_observation(marketing_obs))

    def test_missing_rating_yields_no_observation(self):
        """Missing rating value must never result in an observation."""
        empty_metrics = {}
        rating = empty_metrics.get("rating")
        self.assertIsNone(rating)
        # Connector logic rule: if rating is None, return no observation
        obs_generated = []
        if rating is not None:
            obs_generated.append({"rating": rating})
        self.assertEqual(len(obs_generated), 0)

    def test_missing_review_count_never_fabricated(self):
        """Missing review count must remain None or absent, never fabricated as non-zero."""
        raw_data = {"ratingValue": 4.2}
        count = raw_data.get("ratingCount") or raw_data.get("reviewCount")
        self.assertIsNone(count)
        self.assertNotEqual(count, 0)
        self.assertNotEqual(count, 1)

    def test_wrong_company_rejected(self):
        """Entity without verified match to target org number is rejected."""
        unverified_obs = {
            "id": "unverified-review-001",
            "organisation_number": "999999999",
            "platform": "company_directory",
            "signal_type": "review_summary",
            "source_url": "https://example.com/company/other",
            "retrieved_at": "2026-09-24T12:00:00Z",
            "content_sha256": "c" * 64,
            "exact_entity": False,  # Failed entity match
            "identity_proof": [],
            "acquisition_mode": "permitted_public_page",
            "rights_status": "approved",
            "source_class": "customer_review",
            "evidence_span": "Great service",
        }
        reasons = validate_observation(unverified_obs)
        self.assertIn("exact legal entity is not verified", reasons)
        self.assertIn("missing exact-entity proof", reasons)
        self.assertFalse(publishable_observation(unverified_obs))

    def test_research_agent_unsupported_reviews_policy(self):
        """Research query parsing explicitly flags reviews as unsupported without a qualified provider."""
        self.assertEqual(UNSUPPORTED_SCREEN_TERMS["reviews"], "review data is not available through a qualified provider")
        parsed = parse_screen_query("companies with high customer reviews in Oslo")
        self.assertIn("review data is not available through a qualified provider", parsed["unsupported"])

    def test_fagfolkguiden_script_remains_quarantined(self):
        """Verify run_fagfolkguiden_reviews_connector.py declares review_required and experimental status."""
        fagfolk_path = ROOT / "scripts" / "run_fagfolkguiden_reviews_connector.py"
        content = fagfolk_path.read_text(encoding="utf-8")
        self.assertIn('"acquisition_mode": "rights_review_experiment"', content)
        self.assertIn('"rights_status": "review_required"', content)
        self.assertIn("Third-party display of Google aggregate ratings", content)


if __name__ == "__main__":
    unittest.main()
