from __future__ import annotations

import copy
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.financial_emission import (
    emit_financial_metrics,
    extract_financial_record,
)


class TestFinancialEmission(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_org = "985589003"
        self.sample_complete_record = {
            "record_id": 6639915,
            "account_type": "SELSKAP",
            "period": {
                "fraDato": "2025-01-01",
                "tilDato": "2025-12-31",
            },
            "currency": "NOK",
            "revenue": 4182614.0,
            "operating_result": -127157.0,
            "profit_before_tax": 4672.0,
            "annual_result": 4672.0,
            "assets": 4587133.0,
            "equity": 3145242.0,
            "debt": 1441891.0,
        }
        self.sample_evidence = {
            "field": "financials",
            "status": "available",
            "source_type": "official_annual_accounts",
            "source_url": f"https://data.brreg.no/regnskapsregisteret/regnskap/{self.sample_org}",
            "retrieved_at": "2026-09-22T13:57:10.622785Z",
            "content_sha256": "aa32fa50d50a0bae69b3c71f4b8bae562752aa49c3c55932c7dcb491dd3907ae",
            "source_row_key": self.sample_org,
            "value": {
                "records": [copy.deepcopy(self.sample_complete_record)],
            },
        }

    def test_complete_financial_record(self) -> None:
        """Test extraction and emission of a full financial record with all fields present."""
        profile = {
            "organisation_number": self.sample_org,
            "name": "TEST AS",
            "evidence": {
                "financials": copy.deepcopy(self.sample_evidence),
            },
        }
        result = emit_financial_metrics(profile)

        # Profile top-level fields
        self.assertEqual(result["revenue"], 4182614.0)
        self.assertEqual(result["operating_result"], -127157.0)
        self.assertEqual(result["profit_before_tax"], 4672.0)
        self.assertEqual(result["annual_result"], 4672.0)
        self.assertEqual(result["assets"], 4587133.0)
        self.assertEqual(result["equity"], 3145242.0)
        self.assertEqual(result["debt"], 1441891.0)
        self.assertEqual(result["currency"], "NOK")
        self.assertEqual(result["reporting_period_from"], "2025-01-01")
        self.assertEqual(result["reporting_period_to"], "2025-12-31")

        # Structured financials object
        fin = result["financials"]
        self.assertIsNotNone(fin)
        self.assertEqual(fin["organisation_number"], self.sample_org)
        self.assertEqual(fin["status"], "available")
        self.assertEqual(fin["revenue"], 4182614.0)
        self.assertEqual(fin["annual_result"], 4672.0)
        self.assertEqual(len(fin["records"]), 1)
        self.assertEqual(fin["records"][0]["record_id"], 6639915)
        self.assertEqual(fin["records"][0]["account_type"], "SELSKAP")

    def test_partial_financial_record_preserves_none_and_never_calculates(self) -> None:
        """Test that missing metrics remain None, zero is preserved as 0, and debt is never calculated."""
        partial_record = {
            "record_id": 6812972,
            "account_type": "SELSKAP",
            "period": {
                "fraDato": "2025-01-01",
                "tilDato": "2025-12-31",
            },
            "currency": "NOK",
            "revenue": None,  # explicitly missing in registry
            "operating_result": 0.0,  # legitimate zero
            "profit_before_tax": -6500.0,
            "annual_result": -6500.0,
            "assets": 60000.0,
            "equity": 23500.0,
            "debt": None,  # test missing debt is NOT calculated from assets - equity
        }
        profile = {
            "organisation_number": self.sample_org,
            "name": "TEST AS",
            "evidence": {
                "financials": {
                    "field": "financials",
                    "status": "available",
                    "source_type": "official_annual_accounts",
                    "source_url": f"https://data.brreg.no/regnskapsregisteret/regnskap/{self.sample_org}",
                    "retrieved_at": "2026-09-22T13:57:10Z",
                    "content_sha256": "hash123",
                    "value": {"records": [partial_record]},
                }
            },
        }
        result = emit_financial_metrics(profile)

        # Revenue was None -> must remain None, NEVER 0.0
        self.assertIsNone(result["revenue"])
        self.assertIsNone(result["financials"]["revenue"])

        # Operating result was 0.0 -> must remain 0.0
        self.assertEqual(result["operating_result"], 0.0)

        # Debt was None -> must remain None, NEVER calculated as 60000 - 23500 = 36500
        self.assertIsNone(result["debt"])
        self.assertIsNone(result["financials"]["debt"])

    def test_missing_financial_evidence_leaves_fields_none(self) -> None:
        """Test handling when financial evidence is missing, source_error, or not_found."""
        for status in ["not_found", "source_error", "not_fetched"]:
            profile = {
                "organisation_number": self.sample_org,
                "name": "TEST AS",
                "evidence": {
                    "financials": {
                        "field": "financials",
                        "status": status,
                        "value": None,
                    }
                },
            }
            result = emit_financial_metrics(profile)
            self.assertIsNone(result["financials"])
            self.assertIsNone(result["revenue"])
            self.assertIsNone(result["operating_result"])
            self.assertIsNone(result["annual_result"])
            self.assertIsNone(result["assets"])
            self.assertIsNone(result["equity"])
            self.assertIsNone(result["debt"])
            self.assertIsNone(result["reporting_period_from"])
            self.assertIsNone(result["reporting_period_to"])

        # Completely absent evidence
        empty_profile = {"organisation_number": self.sample_org, "name": "EMPTY AS"}
        result_empty = emit_financial_metrics(empty_profile)
        self.assertIsNone(result_empty["financials"])
        self.assertIsNone(result_empty["revenue"])

    def test_multiple_financial_records_preserved(self) -> None:
        """Test that multiple financial records in evidence are all preserved in order."""
        rec_2025 = copy.deepcopy(self.sample_complete_record)
        rec_2024 = copy.deepcopy(self.sample_complete_record)
        rec_2024["record_id"] = 5555555
        rec_2024["period"] = {"fraDato": "2024-01-01", "tilDato": "2024-12-31"}
        rec_2024["revenue"] = 3500000.0

        ev = copy.deepcopy(self.sample_evidence)
        ev["value"]["records"] = [rec_2025, rec_2024]

        profile = {
            "organisation_number": self.sample_org,
            "evidence": {"financials": ev},
        }
        result = emit_financial_metrics(profile)

        # Both records preserved in order
        records = result["financials"]["records"]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["reporting_period_to"], "2025-12-31")
        self.assertEqual(records[0]["revenue"], 4182614.0)
        self.assertEqual(records[1]["reporting_period_to"], "2024-12-31")
        self.assertEqual(records[1]["revenue"], 3500000.0)

        # Latest record (index 0) populates top-level scalar fields
        self.assertEqual(result["revenue"], 4182614.0)
        self.assertEqual(result["reporting_period_to"], "2025-12-31")

    def test_entity_number_mismatch_rejection(self) -> None:
        """Test strict rejection if financial evidence does not match profile organisation number."""
        different_org = "123456789"
        mismatched_url_ev = copy.deepcopy(self.sample_evidence)
        mismatched_url_ev["source_url"] = f"https://data.brreg.no/regnskapsregisteret/regnskap/{different_org}"

        profile = {
            "organisation_number": self.sample_org,
            "evidence": {"financials": mismatched_url_ev},
        }
        with self.assertRaises(ValueError) as ctx:
            emit_financial_metrics(profile)
        self.assertIn("Financial evidence entity mismatch", str(ctx.exception))

        # Test source_row_key mismatch
        mismatched_key_ev = copy.deepcopy(self.sample_evidence)
        mismatched_key_ev["source_row_key"] = different_org
        profile_key = {
            "organisation_number": self.sample_org,
            "evidence": {"financials": mismatched_key_ev},
        }
        with self.assertRaises(ValueError) as ctx:
            emit_financial_metrics(profile_key)
        self.assertIn("Financial evidence entity mismatch", str(ctx.exception))

    def test_preservation_of_source_metadata(self) -> None:
        """Test that source_url, source_type, retrieved_at, and content_sha256 are strictly preserved."""
        profile = {
            "organisation_number": self.sample_org,
            "evidence": {"financials": copy.deepcopy(self.sample_evidence)},
        }
        result = emit_financial_metrics(profile)

        fin = result["financials"]
        self.assertEqual(fin["source_url"], self.sample_evidence["source_url"])
        self.assertEqual(fin["source_type"], self.sample_evidence["source_type"])
        self.assertEqual(fin["retrieved_at"], self.sample_evidence["retrieved_at"])
        self.assertEqual(fin["content_sha256"], self.sample_evidence["content_sha256"])

        rec = fin["records"][0]
        self.assertEqual(rec["source_url"], self.sample_evidence["source_url"])
        self.assertEqual(rec["source_type"], self.sample_evidence["source_type"])
        self.assertEqual(rec["retrieved_at"], self.sample_evidence["retrieved_at"])
        self.assertEqual(rec["content_sha256"], self.sample_evidence["content_sha256"])

    def test_deterministic_output_and_idempotence(self) -> None:
        """Test that repeated calls produce identical, deterministic results without side effects."""
        profile = {
            "organisation_number": self.sample_org,
            "evidence": {"financials": copy.deepcopy(self.sample_evidence)},
        }
        res1 = emit_financial_metrics(copy.deepcopy(profile))
        res2 = emit_financial_metrics(copy.deepcopy(profile))
        self.assertEqual(res1, res2)

        # Idempotence: running on an already-emitted profile yields the exact same profile
        res3 = emit_financial_metrics(res1)
        self.assertEqual(res1, res3)

    def test_no_network_requests_during_emission(self) -> None:
        """Test that financial emission strictly executes in-memory without making any network calls."""
        profile = {
            "organisation_number": self.sample_org,
            "evidence": {"financials": copy.deepcopy(self.sample_evidence)},
        }
        # Intercept socket creation
        with patch("socket.socket") as mock_socket:
            mock_socket.side_effect = AssertionError("Network call attempted during financial emission!")
            result = emit_financial_metrics(profile)
            self.assertIsNotNone(result["financials"])
            self.assertEqual(result["revenue"], 4182614.0)
            mock_socket.assert_not_called()

    def test_original_evidence_unmodified(self) -> None:
        """Test that original evidence dictionary and its contents are never mutated or destroyed."""
        original_evidence = copy.deepcopy(self.sample_evidence)
        profile = {
            "organisation_number": self.sample_org,
            "evidence": {"financials": copy.deepcopy(self.sample_evidence)},
        }
        result = emit_financial_metrics(profile)
        self.assertEqual(result["evidence"]["financials"], original_evidence)


if __name__ == "__main__":
    unittest.main()
