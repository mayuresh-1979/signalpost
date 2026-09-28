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

from norway_company_agent.contact_registration_emission import is_csv_quote_shifted
from norway_company_agent.purpose_vat_audit_emission import (
    emit_purpose_vat_audit_metrics,
    extract_audit_record,
    extract_purpose_activity_record,
    extract_vat_record,
)


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
            "erIKonsern": "false",
            "vedtektsfestetFormaal": "Utvikling og salg av programvare samt det som naturlig står i forbindelse med dette.",
            "aktivitet": "Programvareutvikling og IT-konsulentvirksomhet.",
            "registrertIMvaRegisteret": "true",
            "registreringsdatoMerverdiavgiftsregisteret": "2018-05-01",
            "registreringsdatoMerverdiavgiftsregisteretEnhetsregisteret": "2018-05-14",
            "frivilligMvaRegistrertBeskrivelser": "Utleier av bygg eller anlegg",
            "registreringsdatoFrivilligMerverdiavgiftsregisteret": "2019-01-10",
            "fravalgRevisjonDato": "2018-06-01",
            "fravalgRevisjonBeslutningsDato": "2018-05-20",
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


class TestPurposeVatAuditEmission(unittest.TestCase):
    def test_clean_purpose_activity_vat_and_audit_extraction(self) -> None:
        profile = _make_profile()
        emit_purpose_vat_audit_metrics(profile)

        # 1. Purpose & operational activity
        pa = profile["purpose_activity"]
        self.assertIsNotNone(pa)
        assert pa is not None
        self.assertEqual(pa["organisation_number"], "985589003")
        self.assertEqual(
            pa["statutory_purpose"],
            "Utvikling og salg av programvare samt det som naturlig står i forbindelse med dette.",
        )
        self.assertEqual(
            pa["operational_activity"],
            "Programvareutvikling og IT-konsulentvirksomhet.",
        )
        self.assertEqual(
            profile["statutory_purpose"],
            "Utvikling og salg av programvare samt det som naturlig står i forbindelse med dette.",
        )
        self.assertEqual(
            profile["operational_activity"],
            "Programvareutvikling og IT-konsulentvirksomhet.",
        )
        self.assertEqual(
            pa["source_url"],
            "https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv",
        )
        self.assertEqual(pa["source_type"], "official_registry_bulk")
        self.assertEqual(pa["source_class"], "official_registry_bulk")
        self.assertEqual(pa["retrieved_at"], "2026-09-22T13:56:52.805088Z")

        # 2. MVA / VAT
        vat = profile["vat"]
        self.assertIsNotNone(vat)
        assert vat is not None
        self.assertIs(vat["registered"], True)
        self.assertEqual(vat["registered_date"], "2018-05-01")
        self.assertEqual(vat["enhetsregisteret_registered_date"], "2018-05-14")
        self.assertEqual(vat["voluntary_descriptions"], "Utleier av bygg eller anlegg")
        self.assertEqual(vat["voluntary_registered_date"], "2019-01-10")
        self.assertIs(profile["vat_registered"], True)
        self.assertEqual(profile["vat_registered_date"], "2018-05-01")
        self.assertEqual(profile["vat_enhetsregisteret_registered_date"], "2018-05-14")
        self.assertEqual(
            profile["vat_voluntary_descriptions"], "Utleier av bygg eller anlegg"
        )
        self.assertEqual(profile["vat_voluntary_registered_date"], "2019-01-10")

        # 3. Audit metadata
        aud = profile["audit"]
        self.assertIsNotNone(aud)
        assert aud is not None
        self.assertEqual(aud["exemption_date"], "2018-06-01")
        self.assertEqual(aud["decision_date"], "2018-05-20")
        self.assertEqual(profile["audit_exemption_date"], "2018-06-01")
        self.assertEqual(profile["audit_decision_date"], "2018-05-20")

    def test_explicit_false_preserved_and_missing_remains_missing_without_inference(self) -> None:
        # Explicit registrertIMvaRegisteret="false" with empty dates and empty audit/purpose
        profile = _make_profile(
            registry_value={
                "organisasjonsnummer": "985589003",
                "paategninger": "false",
                "erIKonsern": "false",
                "vedtektsfestetFormaal": "",
                "aktivitet": "",
                "registrertIMvaRegisteret": "false",
                "registreringsdatoMerverdiavgiftsregisteret": "",
                "registreringsdatoMerverdiavgiftsregisteretEnhetsregisteret": "",
                "frivilligMvaRegistrertBeskrivelser": "",
                "registreringsdatoFrivilligMerverdiavgiftsregisteret": "",
                "fravalgRevisjonDato": "",
                "fravalgRevisjonBeslutningsDato": "",
            }
        )
        emit_purpose_vat_audit_metrics(profile)

        # Purpose & activity completely missing -> None
        self.assertIsNone(profile["purpose_activity"])
        self.assertIsNone(profile["statutory_purpose"])
        self.assertIsNone(profile["operational_activity"])

        # MVA explicit false is preserved as False; missing dates/voluntary remain None
        self.assertIsNotNone(profile["vat"])
        self.assertIs(profile["vat"]["registered"], False)
        self.assertIs(profile["vat_registered"], False)
        self.assertIsNone(profile["vat_registered_date"])
        self.assertIsNone(profile["vat_enhetsregisteret_registered_date"])
        self.assertIsNone(profile["vat_voluntary_descriptions"])
        self.assertIsNone(profile["vat_voluntary_registered_date"])

        # Audit completely missing -> None (never inferred as False)
        self.assertIsNone(profile["audit"])
        self.assertIsNone(profile["audit_exemption_date"])
        self.assertIsNone(profile["audit_decision_date"])

        # When registrertIMvaRegisteret itself is missing (""), vat_registered must be None, NOT False
        all_empty = _make_profile(
            registry_value={
                "organisasjonsnummer": "985589003",
                "paategninger": "false",
                "erIKonsern": "false",
                "registrertIMvaRegisteret": "",
            }
        )
        emit_purpose_vat_audit_metrics(all_empty)
        self.assertIsNone(all_empty["vat"])
        self.assertIsNone(all_empty["vat_registered"])

    def test_date_and_type_validation_rejects_malformed_values(self) -> None:
        malformed = _make_profile(
            registry_value={
                "organisasjonsnummer": "985589003",
                "paategninger": "false",
                "erIKonsern": "false",
                "vedtektsfestetFormaal": "2020-01-01",
                "aktivitet": "false",
                "registrertIMvaRegisteret": "not_a_boolean",
                "registreringsdatoMerverdiavgiftsregisteret": "2021-02-30",
                "registreringsdatoMerverdiavgiftsregisteretEnhetsregisteret": "not-a-date",
                "frivilligMvaRegistrertBeskrivelser": "false",
                "registreringsdatoFrivilligMerverdiavgiftsregisteret": "30000.00",
                "fravalgRevisjonDato": "false",
                "fravalgRevisjonBeslutningsDato": "Journalistikk,bokskriving",
            }
        )
        emit_purpose_vat_audit_metrics(malformed)
        self.assertIsNone(malformed["purpose_activity"])
        self.assertIsNone(malformed["statutory_purpose"])
        self.assertIsNone(malformed["operational_activity"])
        self.assertIsNone(malformed["vat"])
        self.assertIsNone(malformed["vat_registered"])
        self.assertIsNone(malformed["audit"])
        self.assertIsNone(malformed["audit_exemption_date"])
        self.assertIsNone(malformed["audit_decision_date"])

    def test_entity_anchoring_and_no_cross_company_leakage(self) -> None:
        bad_row_key = _make_profile(org="985589003", source_row_key="999999999")
        with self.assertRaises(ValueError):
            extract_purpose_activity_record(bad_row_key)
        with self.assertRaises(ValueError):
            extract_vat_record(bad_row_key)
        with self.assertRaises(ValueError):
            extract_audit_record(bad_row_key)

        bad_inner_org = _make_profile(
            org="985589003",
            registry_value={"organisasjonsnummer": "123456789"},
        )
        with self.assertRaises(ValueError):
            emit_purpose_vat_audit_metrics(bad_inner_org)

        # Two distinct companies do not leak values into each other
        company_a = _make_profile(org="985589003")
        company_b = _make_profile(
            org="916340257",
            registry_value={
                "organisasjonsnummer": "916340257",
                "paategninger": "false",
                "erIKonsern": "false",
                "vedtektsfestetFormaal": "Annet formål AS.",
                "aktivitet": "Annen aktivitet.",
                "registrertIMvaRegisteret": "false",
            },
        )
        emit_purpose_vat_audit_metrics(company_a)
        emit_purpose_vat_audit_metrics(company_b)
        self.assertNotEqual(company_a["statutory_purpose"], company_b["statutory_purpose"])
        self.assertEqual(company_b["purpose_activity"]["organisation_number"], "916340257")
        self.assertEqual(company_b["vat"]["organisation_number"], "916340257")

    def test_csv_shift_protection_on_998600421_914882036_926768026(self) -> None:
        shifted_fixtures = [
            (
                "998600421",
                {
                    "organisasjonsnummer": "998600421",
                    "paategninger": " og rådgivning.",
                    "erIKonsern": "",
                    "registrertIMvaRegisteret": "true",
                    "registreringsdatoMerverdiavgiftsregisteret": "2021-07-01",
                    "registreringsdatoMerverdiavgiftsregisteretEnhetsregisteret": "2021-07-19",
                    "frivilligMvaRegistrertBeskrivelser": "",
                    "registreringsdatoFrivilligMerverdiavgiftsregisteret": "",
                    "vedtektsfestetFormaal": 'Å drive "management for hire""',
                    "aktivitet": " strategi-",
                    "fravalgRevisjonDato": "false",
                    "fravalgRevisjonBeslutningsDato": "",
                    "null": [""],
                },
            ),
            (
                "914882036",
                {
                    "organisasjonsnummer": "914882036",
                    "paategninger": " konserter",
                    "erIKonsern": "false",
                    "registrertIMvaRegisteret": "true",
                    "registreringsdatoMerverdiavgiftsregisteret": "2015-01-01",
                    "registreringsdatoMerverdiavgiftsregisteretEnhetsregisteret": "2015-05-06",
                    "frivilligMvaRegistrertBeskrivelser": "",
                    "registreringsdatoFrivilligMerverdiavgiftsregisteret": "",
                    "vedtektsfestetFormaal": 'Journalistikk, bokskriving, "bokbading""',
                    "aktivitet": " foredragsvirksomhet",
                    "fravalgRevisjonDato": ' herunder deltakelse i andre selskap med lignende virksomhet."',
                    "fravalgRevisjonBeslutningsDato": 'Journalistikk,bokskriving,"bokbading""',
                    "null": ["false", "30000.00", "30"],
                },
            ),
            (
                "926768026",
                {
                    "organisasjonsnummer": "926768026",
                    "paategninger": "30000.00",
                    "erIKonsern": "NOK",
                    "registrertIMvaRegisteret": "false",
                    "registreringsdatoMerverdiavgiftsregisteret": "",
                    "registreringsdatoMerverdiavgiftsregisteretEnhetsregisteret": "",
                    "frivilligMvaRegistrertBeskrivelser": "",
                    "registreringsdatoFrivilligMerverdiavgiftsregisteret": "",
                    "vedtektsfestetFormaal": 'Drift av bandet "Three Souls"" og annet som faller naturlig ved dette."',
                    "aktivitet": 'Bandet "Three Souls"" spiller en rekke konserter',
                    "fravalgRevisjonDato": "2021-02-20",  # Even if a valid ISO date shifted into col 69, row-level guard blocks it
                    "fravalgRevisjonBeslutningsDato": "2021-02-20",
                    "null": ["2021-03-11", ""],
                },
            ),
        ]
        for org, reg_val in shifted_fixtures:
            self.assertTrue(is_csv_quote_shifted(reg_val))
            profile = _make_profile(org=org, registry_value=reg_val)
            emit_purpose_vat_audit_metrics(profile)
            # Columns >= 64 (purpose, activity, audit) MUST be blocked on shifted rows
            self.assertIsNone(profile["purpose_activity"])
            self.assertIsNone(profile["statutory_purpose"])
            self.assertIsNone(profile["operational_activity"])
            self.assertIsNone(profile["audit"])
            self.assertIsNone(profile["audit_exemption_date"])
            self.assertIsNone(profile["audit_decision_date"])
            # Columns 39-43 (MVA, strictly before column 64) are unshifted and validated
            self.assertIsNotNone(profile["vat"])

        # Also test against the real corpus rows in out/profiles.jsonl
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
                emit_purpose_vat_audit_metrics(row)
                self.assertIsNone(row["purpose_activity"])
                self.assertIsNone(row["statutory_purpose"])
                self.assertIsNone(row["operational_activity"])
                self.assertIsNone(row["audit"])
                self.assertIsNone(row["audit_exemption_date"])
                self.assertIsNone(row["audit_decision_date"])

    def test_determinism_evidence_preservation_and_zero_network(self) -> None:
        profile_a = _make_profile()
        profile_b = copy.deepcopy(profile_a)
        original_evidence = copy.deepcopy(profile_a["evidence"])

        with patch("urllib.request.urlopen", side_effect=AssertionError("Network access prohibited")):
            emit_purpose_vat_audit_metrics(profile_a)
            emit_purpose_vat_audit_metrics(profile_b)
            emit_purpose_vat_audit_metrics(profile_b)

        self.assertEqual(profile_a, profile_b)
        self.assertEqual(profile_a["evidence"], original_evidence)


if __name__ == "__main__":
    unittest.main()
