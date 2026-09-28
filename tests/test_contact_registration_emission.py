from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.contact_registration_emission import (
    emit_contact_registration_metrics,
    extract_business_address,
    extract_contact_channels,
    extract_postal_address,
    extract_registration_dates,
    get_safe_bulk_field,
    is_csv_quote_shifted,
)


class TestContactRegistrationEmission(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_org = "985589003"
        self.sample_registry_live = {
            "field": "registry_live",
            "status": "available",
            "source_type": "official_registry_live",
            "source_url": f"https://data.brreg.no/enhetsregisteret/api/enheter/{self.sample_org}",
            "retrieved_at": "2026-09-22T13:57:10.000000Z",
            "content_sha256": "b" * 64,
            "source_row_key": self.sample_org,
            "value": {
                "organisation_number": self.sample_org,
                "name": "ARKITEKTFIRMA JON VIKØREN AS",
                "legal_form": "AS",
                "business_address": {
                    "land": "Norge",
                    "landkode": "NO",
                    "postnummer": "6893",
                    "poststed": "VIK I SOGN",
                    "adresse": ["Tomtebu 2"],
                    "kommune": "VIK",
                    "kommunenummer": "4639",
                },
                "postal_address": {
                    "land": "Norge",
                    "landkode": "NO",
                    "postnummer": "2001",
                    "poststed": "LILLESTRØM",
                    "adresse": ["c/o BORI BBL", "Postboks 323"],
                    "kommune": "LILLESTRØM",
                    "kommunenummer": "3205",
                },
            },
        }
        self.sample_registry_bulk = {
            "field": "registry",
            "status": "available",
            "source_type": "official_registry_bulk",
            "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv",
            "retrieved_at": "2026-09-22T13:56:50.000000Z",
            "content_sha256": "a" * 64,
            "source_row_key": self.sample_org,
            "value": {
                "organisasjonsnummer": self.sample_org,
                "navn": "ARKITEKTFIRMA JON VIKØREN AS",
                "hjemmeside": "https://example.no",
                "epostadresse": "post@arkjv.no",
                "telefon": "57 69 89 50",
                "mobil": "908 21 983",
                "registreringsdatoenhetsregisteret": "2003-04-22",
                "stiftelsesdato": "2003-03-10",
                "vedtektsdato": "2020-05-01",
                "registrertIForetaksregisteret": "true",
                "registreringsdatoForetaksregisteret": "2003-04-25",
                "paategninger": "false",
                "erIKonsern": "false",
            },
        }

    def _make_profile(self) -> dict:
        return {
            "organisation_number": self.sample_org,
            "name": "ARKITEKTFIRMA JON VIKØREN AS",
            "website": "https://example.no",
            "evidence": {
                "registry_live": copy.deepcopy(self.sample_registry_live),
                "registry": copy.deepcopy(self.sample_registry_bulk),
            },
        }

    # 1. Business address emitted from registry_live
    def test_business_address_emitted_from_registry_live(self) -> None:
        profile = self._make_profile()
        # Omit kommune/kommunenummer on a partial address to prove missing components are not fabricated
        del profile["evidence"]["registry_live"]["value"]["business_address"]["kommune"]
        result = emit_contact_registration_metrics(profile)

        ba = result["business_address"]
        self.assertIsNotNone(ba)
        self.assertEqual(ba["organisation_number"], self.sample_org)
        self.assertEqual(ba["adresse"], ["Tomtebu 2"])
        self.assertEqual(ba["postnummer"], "6893")
        self.assertEqual(ba["poststed"], "VIK I SOGN")
        self.assertNotIn("kommune", ba)
        self.assertEqual(ba["kommunenummer"], "4639")
        self.assertEqual(ba["land"], "Norge")
        self.assertEqual(ba["landkode"], "NO")
        self.assertEqual(ba["source_url"], self.sample_registry_live["source_url"])
        self.assertEqual(ba["retrieved_at"], self.sample_registry_live["retrieved_at"])
        self.assertEqual(ba["content_sha256"], self.sample_registry_live["content_sha256"])

    # 2 & 3 & 4. Postal address emitted when present, remains None when absent, never copies business_address
    def test_postal_address_present_and_absent_never_copies_business(self) -> None:
        # Present
        profile = self._make_profile()
        result = emit_contact_registration_metrics(profile)
        pa = result["postal_address"]
        self.assertIsNotNone(pa)
        self.assertEqual(pa["poststed"], "LILLESTRØM")
        self.assertEqual(pa["adresse"], ["c/o BORI BBL", "Postboks 323"])
        self.assertEqual(pa["organisation_number"], self.sample_org)

        # Absent: must remain None and never copy business_address
        profile_no_postal = self._make_profile()
        profile_no_postal["evidence"]["registry_live"]["value"]["postal_address"] = None
        res_no_postal = emit_contact_registration_metrics(profile_no_postal)
        self.assertIsNotNone(res_no_postal["business_address"])
        self.assertIsNone(res_no_postal["postal_address"])

    # 5, 6, 7, 8. Official email, phone, mobile emitted only from retained evidence; no inference or mailto/tel
    def test_contact_channels_emitted_strictly_from_retained_evidence(self) -> None:
        profile = self._make_profile()
        result = emit_contact_registration_metrics(profile)
        self.assertEqual(result["official_email"], "post@arkjv.no")
        self.assertEqual(result["official_phone"], "57 69 89 50")
        self.assertEqual(result["official_mobile"], "908 21 983")

        # When empty in registry bulk, even if website/roles exist, must NOT infer contacts
        profile_empty = self._make_profile()
        profile_empty["evidence"]["registry"]["value"]["epostadresse"] = ""
        profile_empty["evidence"]["registry"]["value"]["telefon"] = ""
        profile_empty["evidence"]["registry"]["value"]["mobil"] = ""
        res_empty = emit_contact_registration_metrics(profile_empty)
        self.assertIsNone(res_empty["official_email"])
        self.assertIsNone(res_empty["official_phone"])
        self.assertIsNone(res_empty["official_mobile"])

        # Reject mailto: or tel: prefixes if passed
        profile_scheme = self._make_profile()
        profile_scheme["evidence"]["registry"]["value"]["epostadresse"] = "mailto:post@arkjv.no"
        profile_scheme["evidence"]["registry"]["value"]["telefon"] = "tel:+4757698950"
        res_scheme = emit_contact_registration_metrics(profile_scheme)
        self.assertIsNone(res_scheme["official_email"])
        self.assertIsNone(res_scheme["official_phone"])

    # 9, 10, 11, 12. Registration dates & independent Foretaksregisteret boolean
    def test_registration_dates_and_independent_boolean(self) -> None:
        profile = self._make_profile()
        result = emit_contact_registration_metrics(profile)
        self.assertEqual(result["registration_date"], "2003-04-22")
        self.assertEqual(result["foundation_date"], "2003-03-10")
        self.assertEqual(result["articles_date"], "2020-05-01")
        self.assertEqual(result["foretaksregisteret_date"], "2003-04-25")
        self.assertIs(result["foretaksregisteret_registered"], True)

        # Malformed dates rejected to None; missing dates remain None; boolean preserved independently
        profile_bad = self._make_profile()
        val = profile_bad["evidence"]["registry"]["value"]
        val["registreringsdatoenhetsregisteret"] = "2003/04/22"
        val["stiftelsesdato"] = "2026-02-30"  # invalid calendar date
        val["vedtektsdato"] = ""
        val["registreringsdatoForetaksregisteret"] = "not-a-date"
        val["registrertIForetaksregisteret"] = "false"

        res_bad = emit_contact_registration_metrics(profile_bad)
        self.assertIsNone(res_bad["registration_date"])
        self.assertIsNone(res_bad["foundation_date"])
        self.assertIsNone(res_bad["articles_date"])
        self.assertIsNone(res_bad["foretaksregisteret_date"])
        self.assertIs(res_bad["foretaksregisteret_registered"], False)

        # Even if date is present, missing boolean is NOT derived from date
        profile_no_bool = self._make_profile()
        profile_no_bool["evidence"]["registry"]["value"]["registrertIForetaksregisteret"] = ""
        res_no_bool = emit_contact_registration_metrics(profile_no_bool)
        self.assertEqual(res_no_bool["foretaksregisteret_date"], "2003-04-25")
        self.assertIsNone(res_no_bool["foretaksregisteret_registered"])

    # 13. Entity safety: mismatched organisation number rejected
    def test_entity_number_mismatch_rejected(self) -> None:
        other_org = "123456789"

        # Mismatched registry_live URL
        p1 = self._make_profile()
        p1["evidence"]["registry_live"]["source_url"] = (
            f"https://data.brreg.no/enhetsregisteret/api/enheter/{other_org}"
        )
        with self.assertRaises(ValueError):
            emit_contact_registration_metrics(p1)

        # Mismatched registry_live value org
        p2 = self._make_profile()
        p2["evidence"]["registry_live"]["value"]["organisation_number"] = other_org
        with self.assertRaises(ValueError):
            emit_contact_registration_metrics(p2)

        # Mismatched registry bulk source_row_key
        p3 = self._make_profile()
        p3["evidence"]["registry"]["source_row_key"] = other_org
        with self.assertRaises(ValueError):
            emit_contact_registration_metrics(p3)

        # Mismatched registry bulk value organisasjonsnummer
        p4 = self._make_profile()
        p4["evidence"]["registry"]["value"]["organisasjonsnummer"] = other_org
        with self.assertRaises(ValueError):
            emit_contact_registration_metrics(p4)

    # 14. CSV-shift safety on 998600421, 914882036, 926768026
    def test_csv_shift_safety_on_known_corrupted_rows(self) -> None:
        shifted_orgs = {"998600421", "914882036", "926768026"}
        profiles_path = ROOT / "out" / "profiles.jsonl"
        found = {}
        with profiles_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                if row["organisation_number"] in shifted_orgs:
                    found[row["organisation_number"]] = row

        self.assertEqual(set(found.keys()), shifted_orgs)

        for org, row in found.items():
            bulk_val = row["evidence"]["registry"]["value"]
            self.assertTrue(is_csv_quote_shifted(bulk_val), f"Expected {org} to be detected as quote-shifted")

            # Columns >= 64 must be blocked by get_safe_bulk_field
            for col64_plus in (
                "vedtektsfestetFormaal",
                "aktivitet",
                "paategninger",
                "fravalgRevisjonDato",
                "erIKonsern",
                "kapital.belop",
                "kapital.valuta",
                "kapital.antallAksjer",
                "kapital.type",
                "kapital.innfortDato",
            ):
                self.assertIsNone(
                    get_safe_bulk_field(bulk_val, col64_plus),
                    f"Column {col64_plus} >= 64 must be blocked on shifted org {org}",
                )

            # Clean registry_live address and unshifted < 64 fields must still emit cleanly
            emitted = emit_contact_registration_metrics(copy.deepcopy(row))
            self.assertIsNotNone(emitted["business_address"])
            self.assertEqual(emitted["business_address"]["organisation_number"], org)
            self.assertIsNotNone(emitted["registration_date"])
            self.assertIsNotNone(emitted["foundation_date"])
            self.assertIsNotNone(emitted["articles_date"])
            self.assertIsNotNone(emitted["foretaksregisteret_date"])
            self.assertIs(emitted["foretaksregisteret_registered"], True)

    # 15. Determinism, original evidence unchanged, and zero network requests
    def test_determinism_evidence_preservation_and_zero_network(self) -> None:
        profile = self._make_profile()
        original_evidence = copy.deepcopy(profile["evidence"])

        with patch("socket.socket") as mock_socket:
            mock_socket.side_effect = AssertionError("Network call attempted during Phase 21 emission!")
            out1 = emit_contact_registration_metrics(copy.deepcopy(profile))
            out2 = emit_contact_registration_metrics(copy.deepcopy(profile))
            out3 = emit_contact_registration_metrics(copy.deepcopy(out1))
            mock_socket.assert_not_called()

        self.assertEqual(out1, out2)
        self.assertEqual(out1, out3)
        self.assertEqual(out1["evidence"], original_evidence)


if __name__ == "__main__":
    unittest.main()
