from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.capital_emission import (
    emit_capital_metrics,
    extract_capital_record,
)
from norway_company_agent.contact_registration_emission import is_csv_quote_shifted


def _make_profile(
    org: str = "985589003",
    registry_value: dict[str, Any] | None = None,
    *,
    registry_status: str = "available",
    source_row_key: str | None = None,
) -> dict[str, Any]:
    if registry_value is None:
        registry_value = {
            "organisasjonsnummer": org,
            "navn": "TESTSELSKAP AS",
            "paategninger": "false",
            "erIKonsern": "true",
            "kapital.belop": "100000.00",
            "kapital.valuta": "NOK",
            "kapital.innfortDato": "2018-04-12",
            "kapital.antallAksjer": "1000",
            "kapital.type": "Aksjekapital",
            "kapital.innbetalt": "",
            "kapital.fulltInnbetalt": "",
            "kapital.bundet": "",
        }
    return {
        "organisation_number": org,
        "name": "TESTSELSKAP AS",
        "evidence": {
            "registry": {
                "field": "registry",
                "status": registry_status,
                "source_type": "official_registry_bulk",
                "source_class": "official_registry_bulk",
                "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv",
                "retrieved_at": "2026-09-22T13:56:52.805088Z",
                "effective_at": None,
                "as_of": None,
                "content_sha256": "2b45e690625a82d90efd9b44536e66fbaee2b79dd804fe3d6fb9432430774f01",
                "source_row_key": source_row_key if source_row_key is not None else org,
                "value": registry_value,
            }
        },
    }


class TestCapitalEmission(unittest.TestCase):
    def test_basic_extraction_and_convenience_fields(self) -> None:
        profile = _make_profile()
        emit_capital_metrics(profile)

        cap = profile["capital"]
        self.assertIsNotNone(cap)
        assert cap is not None
        self.assertEqual(cap["organisation_number"], "985589003")
        self.assertEqual(cap["amount"], 100000.0)
        self.assertIsInstance(cap["amount"], float)
        self.assertEqual(cap["currency"], "NOK")
        self.assertEqual(cap["registered_date"], "2018-04-12")
        self.assertEqual(cap["share_count"], 1000)
        self.assertIsInstance(cap["share_count"], int)
        self.assertEqual(cap["type"], "Aksjekapital")
        self.assertIsNone(cap["paid_in"])
        self.assertIsNone(cap["fully_paid_in"])
        self.assertIsNone(cap["bound"])
        self.assertEqual(
            cap["source_url"],
            "https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv",
        )
        self.assertEqual(cap["source_type"], "official_registry_bulk")
        self.assertEqual(cap["source_class"], "official_registry_bulk")
        self.assertEqual(cap["retrieved_at"], "2026-09-22T13:56:52.805088Z")
        self.assertIsNone(cap["effective_at"])
        self.assertEqual(
            cap["content_sha256"],
            "2b45e690625a82d90efd9b44536e66fbaee2b79dd804fe3d6fb9432430774f01",
        )

        # Top-level convenience fields
        self.assertEqual(profile["share_capital"], 100000.0)
        self.assertEqual(profile["share_capital_currency"], "NOK")
        self.assertEqual(profile["share_count"], 1000)
        self.assertEqual(profile["capital_registered_date"], "2018-04-12")
        self.assertEqual(profile["capital_type"], "Aksjekapital")

    def test_missing_values_remain_missing(self) -> None:
        # All capital fields empty -> capital is None
        empty_profile = _make_profile(
            registry_value={
                "organisasjonsnummer": "985589003",
                "paategninger": "false",
                "erIKonsern": "false",
                "kapital.belop": "",
                "kapital.valuta": "",
                "kapital.innfortDato": "",
                "kapital.antallAksjer": "",
                "kapital.type": "",
                "kapital.innbetalt": "",
                "kapital.fulltInnbetalt": "",
                "kapital.bundet": "",
            }
        )
        emit_capital_metrics(empty_profile)
        self.assertIsNone(empty_profile["capital"])
        self.assertIsNone(empty_profile["share_capital"])
        self.assertIsNone(empty_profile["share_capital_currency"])
        self.assertIsNone(empty_profile["share_count"])
        self.assertIsNone(empty_profile["capital_registered_date"])
        self.assertIsNone(empty_profile["capital_type"])

        # Partial capital record: missing currency, share_count, date, type remain None (never defaulted)
        partial_profile = _make_profile(
            registry_value={
                "organisasjonsnummer": "985589003",
                "paategninger": "false",
                "erIKonsern": "false",
                "kapital.belop": "122569.75",
                "kapital.valuta": "",
                "kapital.innfortDato": "",
                "kapital.antallAksjer": "",
                "kapital.type": "",
            }
        )
        emit_capital_metrics(partial_profile)
        self.assertIsNotNone(partial_profile["capital"])
        self.assertEqual(partial_profile["share_capital"], 122569.75)
        self.assertIsNone(partial_profile["share_capital_currency"])
        self.assertIsNone(partial_profile["share_count"])
        self.assertIsNone(partial_profile["capital_registered_date"])
        self.assertIsNone(partial_profile["capital_type"])

    def test_type_safety_rejects_malformed_values(self) -> None:
        malformed_profile = _make_profile(
            registry_value={
                "organisasjonsnummer": "985589003",
                "paategninger": "false",
                "erIKonsern": "false",
                "kapital.belop": "2012-08-08",
                "kapital.valuta": "100",
                "kapital.innfortDato": "NOK",
                "kapital.antallAksjer": "32000.00",
                "kapital.type": "32000.00",
                "kapital.innbetalt": "Aksjekapital",
                "kapital.fulltInnbetalt": "NOK",
                "kapital.bundet": "not-a-number",
            }
        )
        emit_capital_metrics(malformed_profile)
        self.assertIsNone(malformed_profile["capital"])
        self.assertIsNone(malformed_profile["share_capital"])
        self.assertIsNone(malformed_profile["share_capital_currency"])
        self.assertIsNone(malformed_profile["share_count"])
        self.assertIsNone(malformed_profile["capital_registered_date"])
        self.assertIsNone(malformed_profile["capital_type"])

    def test_sparse_fields_and_missing_not_zero_or_false(self) -> None:
        # Grunnkapital foundation with explicit paid_in, fully_paid_in=true, bound
        foundation_profile = _make_profile(
            org="976244273",
            registry_value={
                "organisasjonsnummer": "976244273",
                "paategninger": "false",
                "erIKonsern": "false",
                "kapital.belop": "775057.05",
                "kapital.valuta": "NOK",
                "kapital.innfortDato": "2008-11-14",
                "kapital.antallAksjer": "",
                "kapital.type": "Grunnkapital",
                "kapital.innbetalt": "775057.05",
                "kapital.fulltInnbetalt": "true",
                "kapital.bundet": "500000.00",
            },
        )
        emit_capital_metrics(foundation_profile)
        cap = foundation_profile["capital"]
        self.assertIsNotNone(cap)
        assert cap is not None
        self.assertEqual(cap["amount"], 775057.05)
        self.assertEqual(cap["type"], "Grunnkapital")
        self.assertIsNone(cap["share_count"])
        self.assertEqual(cap["paid_in"], 775057.05)
        self.assertIs(cap["fully_paid_in"], True)
        self.assertEqual(cap["bound"], 500000.0)

        # Foundation where innbetalt == belop (800000.00) but fulltInnbetalt is empty (e.g. 977539366):
        # must NOT infer fully_paid_in=True or False, and missing bound must NOT become 0
        unflagged_foundation = _make_profile(
            org="977539366",
            registry_value={
                "organisasjonsnummer": "977539366",
                "paategninger": "false",
                "erIKonsern": "false",
                "kapital.belop": "800000.00",
                "kapital.valuta": "NOK",
                "kapital.innfortDato": "2007-05-10",
                "kapital.antallAksjer": "",
                "kapital.type": "Grunnkapital",
                "kapital.innbetalt": "800000.00",
                "kapital.fulltInnbetalt": "",
                "kapital.bundet": "",
            },
        )
        emit_capital_metrics(unflagged_foundation)
        cap2 = unflagged_foundation["capital"]
        self.assertIsNotNone(cap2)
        assert cap2 is not None
        self.assertEqual(cap2["paid_in"], 800000.0)
        self.assertIsNone(cap2["fully_paid_in"])
        self.assertIsNone(cap2["bound"])

    def test_entity_safety_rejects_mismatched_organisation_numbers(self) -> None:
        bad_row_key = _make_profile(org="985589003", source_row_key="999999999")
        with self.assertRaises(ValueError):
            extract_capital_record(bad_row_key)

        bad_inner_org = _make_profile(
            org="985589003",
            registry_value={
                "organisasjonsnummer": "888888888",
                "paategninger": "false",
                "erIKonsern": "false",
                "kapital.belop": "100000.00",
            },
        )
        with self.assertRaises(ValueError):
            emit_capital_metrics(bad_inner_org)

        missing_org = _make_profile(org="")
        with self.assertRaises(ValueError):
            emit_capital_metrics(missing_org)

    def test_csv_shift_safety_excludes_known_corrupted_rows(self) -> None:
        # Test synthetic shifted rows matching 998600421, 914882036, 926768026
        shifted_fixtures = [
            (
                "998600421",
                {
                    "organisasjonsnummer": "998600421",
                    "paategninger": " og rådgivning.",
                    "erIKonsern": "",
                    "kapital.belop": "2012-08-08",
                    "kapital.valuta": "100",
                    "kapital.innfortDato": "NOK",
                    "kapital.antallAksjer": "",
                    "kapital.type": "false",
                    "kapital.innbetalt": "Aksjekapital",
                    "kapital.fulltInnbetalt": "",
                    "kapital.bundet": "30000.00",
                    "null": [""],
                },
            ),
            (
                "914882036",
                {
                    "organisasjonsnummer": "914882036",
                    "paategninger": " konserter",
                    "erIKonsern": "false",
                    "kapital.belop": " debattledelse",
                    "kapital.valuta": "false",
                    "kapital.innfortDato": "2015-01-29",
                    "kapital.antallAksjer": " investeringsvirksomhet i verdipapir og eiendom",
                    "kapital.type": " samt beslektet virksomhet",
                    "kapital.innbetalt": "",
                    "kapital.fulltInnbetalt": "",
                    "kapital.bundet": ' herunder deltakelse i andre selskap med lignende virksomhet."',
                    "null": ["false", "30000.00", "30"],
                },
            ),
            (
                "926768026",
                {
                    "organisasjonsnummer": "926768026",
                    "paategninger": "30000.00",
                    "erIKonsern": "NOK",
                    "kapital.belop": "2021-02-20",
                    "kapital.valuta": "Aksjekapital",
                    "kapital.innfortDato": "",
                    "kapital.antallAksjer": "false",
                    "kapital.type": "32000.00",
                    "kapital.innbetalt": "",
                    "kapital.fulltInnbetalt": "NOK",
                    "kapital.bundet": "320",
                    "null": ["2021-03-11", ""],
                },
            ),
        ]
        for org, reg_val in shifted_fixtures:
            self.assertTrue(is_csv_quote_shifted(reg_val), f"Expected {org} to be flagged as CSV-shifted")
            profile = _make_profile(org=org, registry_value=reg_val)
            emit_capital_metrics(profile)
            self.assertIsNone(profile["capital"], f"Expected capital=None for shifted {org}")
            self.assertIsNone(profile["share_capital"])
            self.assertIsNone(profile["share_capital_currency"])
            self.assertIsNone(profile["share_count"])
            self.assertIsNone(profile["capital_registered_date"])
            self.assertIsNone(profile["capital_type"])

        # Also verify against the real corpus rows if out/profiles.jsonl exists
        profiles_path = Path("out/profiles.jsonl")
        if profiles_path.exists():
            by_org = {
                row["organisation_number"]: row
                for line in profiles_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
                for row in (json.loads(line),)
            }
            for org in ("998600421", "914882036", "926768026"):
                self.assertIn(org, by_org)
                row = copy.deepcopy(by_org[org])
                emit_capital_metrics(row)
                self.assertIsNone(row["capital"])
                self.assertIsNone(row["share_capital"])
                self.assertIsNone(row["share_capital_currency"])
                self.assertIsNone(row["share_count"])
                self.assertIsNone(row["capital_registered_date"])
                self.assertIsNone(row["capital_type"])

    def test_determinism_evidence_preservation_and_zero_network(self) -> None:
        profile_a = _make_profile()
        profile_b = copy.deepcopy(profile_a)
        original_evidence = copy.deepcopy(profile_a["evidence"])

        with patch("urllib.request.urlopen", side_effect=AssertionError("Network access prohibited")):
            emit_capital_metrics(profile_a)
            emit_capital_metrics(profile_b)
            # Re-run on already-emitted profile for idempotency
            emit_capital_metrics(profile_b)

        self.assertEqual(profile_a, profile_b)
        self.assertEqual(profile_a["evidence"], original_evidence)


if __name__ == "__main__":
    unittest.main()
