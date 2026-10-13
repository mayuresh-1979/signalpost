"""Focused regression tests for Builderr contract export semantics."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("export_builderr_contract.py")
SPEC = importlib.util.spec_from_file_location("export_builderr_contract", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuilderrContractExportTests(unittest.TestCase):
    def test_unfetched_is_not_claimed_as_absent(self):
        self.assertEqual(MODULE.availability({"status": "not_fetched"}), "failed")
        self.assertEqual(MODULE.availability({"status": "not_found"}), "not_available")

    def test_terminal_result_uses_challenge_six_state_vocabulary(self):
        self.assertEqual(MODULE.result_status([{"availability": "available"}], "completed"), "available")
        self.assertEqual(MODULE.result_status([{"availability": "blocked"}], "completed"), "blocked")
        self.assertEqual(MODULE.result_status([{"availability": "ambiguous"}], "completed"), "ambiguous")
        self.assertEqual(MODULE.result_status([{"availability": "not_applicable"}], "completed"), "not_applicable")
        self.assertEqual(MODULE.result_status([{"availability": "not_available"}], "completed"), "not_available")
        self.assertEqual(MODULE.result_status([{"availability": "available"}], "failed"), "failed")

    def test_source_class_prioritizes_official_registry(self):
        self.assertEqual(
            MODULE.source_class({"source_type": "official_company_registry"}),
            "official_registry",
        )
        self.assertEqual(
            MODULE.source_class({"source_type": "verified_company_website"}),
            "company_owned",
        )
        self.assertEqual(
            MODULE.source_class({"source_type": "permitted_public_page"}),
            "permitted_public_page",
        )

    def test_claim_value_removes_nested_provenance(self):
        raw = {
            "address": {"street": "Main 1", "source_url": "https://registry.example/",
                        "retrieved_at": "2026-10-13T00:00:00Z",
                        "content_sha256": "a" * 64},
            "source_type": "official_registry_live",
            "count": 3,
        }
        self.assertEqual(
            MODULE.clean_claim_value(raw),
            {"address": {"street": "Main 1"}, "count": 3},
        )

    def test_available_claim_values_are_cleaned_but_evidence_retained(self):
        envelope = {
            "organisation_number": "123456789",
            "run_id": "test",
            "started_at": "2026-10-13T00:00:00Z",
            "completed_at": "2026-10-13T00:00:01Z",
            "state": "complete",
            "modules": {},
            "profile": {
                "name": "Example AS",
                "business_address": {
                    "street": "Main 1",
                    "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/123456789",
                    "source_type": "official_registry_live",
                    "retrieved_at": "2026-10-13T00:00:00Z",
                    "content_sha256": "a" * 64,
                },
                "evidence": {
                    "registry": {
                        "status": "available",
                        "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/123456789",
                        "source_type": "official_registry_live",
                        "retrieved_at": "2026-10-13T00:00:00Z",
                        "content_sha256": "a" * 64,
                        "value": {"name": "Example AS"},
                    },
                    "registry_live": {
                        "status": "available",
                        "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/123456789",
                        "source_type": "official_registry_live",
                        "retrieved_at": "2026-10-13T00:00:00Z",
                        "content_sha256": "a" * 64,
                        "value": {"address": {"street": "Main 1"}},
                    },
                },
            },
        }
        result = MODULE.build_result(envelope)
        address = next(c for c in result["claims"] if c["field"] == "company.business_address")
        self.assertEqual(result["status"], "available")
        self.assertEqual(address["value"], {"street": "Main 1"})
        self.assertEqual(len(result["evidence"]), 2)
        self.assertEqual({e["source_class"] for e in result["evidence"]}, {"official_registry"})


if __name__ == "__main__":
    unittest.main()
