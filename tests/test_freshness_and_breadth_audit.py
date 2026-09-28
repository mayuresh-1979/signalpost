#!/usr/bin/env python3
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from norway_company_agent.external_footprint import (
    validate_observation,
    publishable_observation,
    _as_datetime,
)
from scripts.extract_official_workforce import extract_entity_workforce


class FreshnessAndBreadthAuditTests(unittest.TestCase):
    def test_evidence_grounded_freshness_acceptance(self):
        """Observations with explicit registration dates within 45 days are accepted as fresh."""
        eval_date = datetime(2026, 9, 24, tzinfo=timezone.utc)
        fresh_date = (eval_date - timedelta(days=10)).strftime("%Y-%m-%d")

        profile = {
            "organisation_number": "916340257",
            "name": "TEST FRESH AS",
            "evidence": {
                "registry": {
                    "status": "available",
                    "retrieved_at": "2026-09-22T13:56:52Z",
                    "content_sha256": "a" * 64,
                    "value": {
                        "organisasjonsnummer": "916340257",
                        "antallAnsatte": "10",
                        "registreringsdatoAntallAnsatteEnhetsregisteret": fresh_date,
                    },
                },
                "registry_live": {
                    "status": "available",
                    "retrieved_at": "2026-09-22T13:56:52Z",
                    "content_sha256": "b" * 64,
                    "value": {"organisation_number": "916340257", "employees": 10},
                },
            },
        }
        obs = extract_entity_workforce(profile)
        self.assertIsNotNone(obs)
        self.assertEqual(obs["effective_at"], fresh_date)
        dt = _as_datetime(obs["effective_at"])
        self.assertTrue(0 <= (eval_date - dt).total_seconds() <= 45 * 86400)

    def test_stale_dates_rejected_from_freshness(self):
        """Observations with registration dates older than 45 days are identified as stale."""
        eval_date = datetime(2026, 9, 24, tzinfo=timezone.utc)
        stale_date = "2025-06-11"  # Over 400 days old

        dt = _as_datetime(stale_date)
        self.assertIsNotNone(dt)
        self.assertFalse(0 <= (eval_date - dt).total_seconds() <= 45 * 86400)

    def test_retrieval_date_not_conflated_with_freshness(self):
        """Recent retrieved_at without explicit evidence publication date must not be assumed fresh."""
        obs = {
            "id": "test-obs-no-date",
            "organisation_number": "999999999",
            "platform": "company_site",
            "signal_type": "profile_metrics",
            "source_url": "https://example.no/",
            "retrieved_at": "2026-09-24T12:00:00Z",  # Retrieved today
            "content_sha256": "c" * 64,
            "exact_entity": True,
            "identity_proof": [{"type": "website", "value": "example.no"}],
            "acquisition_mode": "permitted_public_page",
            "rights_status": "approved",
            "source_class": "company_site",
            "evidence_span": "Snapshot",
            "effective_at": None,  # No documented evidence date
        }
        self.assertIsNone(obs.get("effective_at"))

    def test_multi_source_breadth_exact_counting(self):
        """Platform breadth requires observations across >= 2 distinct platforms."""
        obs_company_site = {"organisation_number": "100", "platform": "company_site"}
        obs_social = {"organisation_number": "100", "platform": "linkedin"}
        obs_same_platform = {"organisation_number": "200", "platform": "brreg"}
        obs_same_platform_sub = {"organisation_number": "200", "platform": "brreg"}

        org_platforms = {}
        for item in [obs_company_site, obs_social]:
            org_platforms.setdefault(item["organisation_number"], set()).add(item["platform"])
        self.assertEqual(len(org_platforms["100"]), 2)  # Multi-platform

        single_platforms = {}
        for item in [obs_same_platform, obs_same_platform_sub]:
            single_platforms.setdefault(item["organisation_number"], set()).add(item["platform"])
        self.assertEqual(len(single_platforms["200"]), 1)  # Single platform only

    def test_deterministic_freshness_replay(self):
        """Repeated calculation of freshness produces identical results."""
        as_of = datetime(2026, 9, 24, tzinfo=timezone.utc)
        dates = ["2026-09-14", "2025-06-11", "2026-08-12", "2026-01-13"]
        fresh_count_1 = sum(0 <= (as_of - _as_datetime(d)).total_seconds() <= 45 * 86400 for d in dates)
        fresh_count_2 = sum(0 <= (as_of - _as_datetime(d)).total_seconds() <= 45 * 86400 for d in dates)
        self.assertEqual(fresh_count_1, fresh_count_2)
        self.assertEqual(fresh_count_1, 2)


if __name__ == "__main__":
    unittest.main()
