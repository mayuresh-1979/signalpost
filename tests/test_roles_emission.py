from __future__ import annotations

import copy
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.roles_emission import (
    emit_roles_metrics,
    extract_role_record,
)


class TestRolesEmission(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_org = "985589003"
        self.sample_roles_raw = [
            {
                "name": "Kaare Vang Jensen",
                "organisation_number": None,
                "role_code": "DAGL",
                "role": "Daglig leder",
                "group_code": "DAGL",
                "group": "Daglig leder",
                "last_changed": "2024-09-09",
                "inactive": False,
            },
            {
                "name": "Lin Marie Vikøren",
                "organisation_number": None,
                "role_code": "LEDE",
                "role": "Styrets leder",
                "group_code": "STYR",
                "group": "Styre",
                "last_changed": "2026-08-19",
                "inactive": False,
            },
            {
                "name": "Kjell Arnstein Vikestad",
                "organisation_number": None,
                "role_code": "MEDL",
                "role": "Styremedlem",
                "group_code": "STYR",
                "group": "Styre",
                "last_changed": "2026-08-19",
                "inactive": False,
            },
            {
                "name": "Ola Varamedlem",
                "organisation_number": None,
                "role_code": "VARA",
                "role": "Varamedlem",
                "group_code": "STYR",
                "group": "Styre",
                "last_changed": "2025-05-10",
                "inactive": False,
            },
            {
                "name": ["REVISJON NORGE AS"],
                "organisation_number": "987654321",
                "role_code": "REVI",
                "role": "Revisor",
                "group_code": "REVI",
                "group": "Revisor",
                "last_changed": "2023-01-15",
                "inactive": False,
            },
            {
                "name": ["ØKONOMI SOGN AS"],
                "organisation_number": "979947143",
                "role_code": "REGN",
                "role": "Regnskapsfører",
                "group_code": "REGN",
                "group": "Regnskapsfører",
                "last_changed": "2003-04-22",
                "inactive": False,
            },
        ]
        self.sample_evidence = {
            "field": "roles",
            "status": "available",
            "source_type": "official_roles",
            "source_url": f"https://data.brreg.no/enhetsregisteret/api/enheter/{self.sample_org}/roller",
            "retrieved_at": "2026-09-22T13:57:11.453695Z",
            "content_sha256": "307d781fabc2c023791172cccae91c49d0fe654413675926fcb3189e5e877c3d",
            "source_row_key": self.sample_org,
            "value": {
                "roles": copy.deepcopy(self.sample_roles_raw),
            },
        }

    # 1. Complete role set
    def test_complete_role_set(self) -> None:
        """Test extraction and emission of a complete role set containing all standard role types."""
        profile = {
            "organisation_number": self.sample_org,
            "name": "TEST AS",
            "evidence": {
                "roles": copy.deepcopy(self.sample_evidence),
            },
        }
        result = emit_roles_metrics(profile)

        # Canonical roles list
        roles = result.get("roles")
        self.assertIsNotNone(roles)
        self.assertEqual(len(roles), 6)

        # Every role must be anchored to the company's organisation_number
        for r in roles:
            self.assertEqual(r["organisation_number"], self.sample_org)
            self.assertEqual(r["company_organisation_number"], self.sample_org)

        # Corporate holders maintain their own organisation_number in holder_organisation_number
        revi_role = next(r for r in roles if r["role_code"] == "REVI")
        self.assertEqual(revi_role["holder_organisation_number"], "987654321")
        self.assertEqual(revi_role["name"], "REVISJON NORGE AS")

        regn_role = next(r for r in roles if r["role_code"] == "REGN")
        self.assertEqual(regn_role["holder_organisation_number"], "979947143")
        self.assertEqual(regn_role["name"], "ØKONOMI SOGN AS")

        # Convenience fields populated
        self.assertIsNotNone(result["board_chair"])
        self.assertEqual(result["board_chair"]["role_code"], "LEDE")
        self.assertEqual(result["board_chair"]["name"], "Lin Marie Vikøren")

        self.assertIsNotNone(result["managing_director"])
        self.assertEqual(result["managing_director"]["role_code"], "DAGL")
        self.assertEqual(result["managing_director"]["name"], "Kaare Vang Jensen")

        self.assertIsNotNone(result["board_members"])
        self.assertEqual(len(result["board_members"]), 1)
        self.assertEqual(result["board_members"][0]["role_code"], "MEDL")

        self.assertIsNotNone(result["deputy_board_members"])
        self.assertEqual(len(result["deputy_board_members"]), 1)
        self.assertEqual(result["deputy_board_members"][0]["role_code"], "VARA")

        self.assertIsNotNone(result["auditors"])
        self.assertEqual(len(result["auditors"]), 1)
        self.assertEqual(result["auditors"][0]["role_code"], "REVI")

        self.assertIsNotNone(result["authorized_accountants"])
        self.assertEqual(len(result["authorized_accountants"]), 1)
        self.assertEqual(result["authorized_accountants"][0]["role_code"], "REGN")

    # 2. CEO/DAGL emission
    def test_ceo_dagl_emission(self) -> None:
        """Test managing_director emission, preference for active record, and None when absent."""
        # Case A: Normal single DAGL
        ev = copy.deepcopy(self.sample_evidence)
        ev["value"]["roles"] = [self.sample_roles_raw[0]]
        profile = {"organisation_number": self.sample_org, "evidence": {"roles": ev}}
        result = emit_roles_metrics(profile)
        self.assertEqual(result["managing_director"]["name"], "Kaare Vang Jensen")
        self.assertEqual(result["managing_director"]["role_code"], "DAGL")

        # Case B: Multiple DAGLs (prefer active)
        inactive_dagl = copy.deepcopy(self.sample_roles_raw[0])
        inactive_dagl["inactive"] = True
        inactive_dagl["name"] = "Former CEO"
        active_dagl = copy.deepcopy(self.sample_roles_raw[0])
        active_dagl["name"] = "Current CEO"
        ev_multi = copy.deepcopy(self.sample_evidence)
        ev_multi["value"]["roles"] = [inactive_dagl, active_dagl]
        profile_multi = {"organisation_number": self.sample_org, "evidence": {"roles": ev_multi}}
        res_multi = emit_roles_metrics(profile_multi)
        self.assertEqual(res_multi["managing_director"]["name"], "Current CEO")

        # Case C: No DAGL in roles
        ev_no_dagl = copy.deepcopy(self.sample_evidence)
        ev_no_dagl["value"]["roles"] = [self.sample_roles_raw[1]]  # only LEDE
        profile_no = {"organisation_number": self.sample_org, "evidence": {"roles": ev_no_dagl}}
        res_no = emit_roles_metrics(profile_no)
        self.assertIsNone(res_no["managing_director"])

    # 3. Board chair/LEDE emission
    def test_board_chair_lede_emission(self) -> None:
        """Test board_chair emission, preference for active record, and None when absent."""
        # Present
        ev = copy.deepcopy(self.sample_evidence)
        ev["value"]["roles"] = [self.sample_roles_raw[1]]
        profile = {"organisation_number": self.sample_org, "evidence": {"roles": ev}}
        result = emit_roles_metrics(profile)
        self.assertIsNotNone(result["board_chair"])
        self.assertEqual(result["board_chair"]["role_code"], "LEDE")
        self.assertEqual(result["board_chair"]["name"], "Lin Marie Vikøren")

        # Absent
        ev_absent = copy.deepcopy(self.sample_evidence)
        ev_absent["value"]["roles"] = [self.sample_roles_raw[0]]  # only DAGL
        profile_absent = {"organisation_number": self.sample_org, "evidence": {"roles": ev_absent}}
        res_absent = emit_roles_metrics(profile_absent)
        self.assertIsNone(res_absent["board_chair"])

    # 4. Board members/MEDL emission
    def test_board_members_medl_emission(self) -> None:
        """Test board_members emission for multiple members, and None when absent."""
        medl_1 = copy.deepcopy(self.sample_roles_raw[2])
        medl_2 = copy.deepcopy(self.sample_roles_raw[2])
        medl_2["name"] = "Second Member"
        ev = copy.deepcopy(self.sample_evidence)
        ev["value"]["roles"] = [medl_1, medl_2]
        profile = {"organisation_number": self.sample_org, "evidence": {"roles": ev}}
        result = emit_roles_metrics(profile)
        self.assertIsNotNone(result["board_members"])
        self.assertEqual(len(result["board_members"]), 2)
        self.assertEqual(result["board_members"][0]["name"], "Kjell Arnstein Vikestad")
        self.assertEqual(result["board_members"][1]["name"], "Second Member")

        # Missingness discipline: absent MEDL must be None, not []
        ev_no_medl = copy.deepcopy(self.sample_evidence)
        ev_no_medl["value"]["roles"] = [self.sample_roles_raw[1]]
        profile_no = {"organisation_number": self.sample_org, "evidence": {"roles": ev_no_medl}}
        res_no = emit_roles_metrics(profile_no)
        self.assertIsNone(res_no["board_members"])

    # 5. Auditor/REVI emission
    def test_auditor_revi_emission(self) -> None:
        """Test statutory auditor REVI emission with corporate holder number, and None when absent."""
        ev = copy.deepcopy(self.sample_evidence)
        ev["value"]["roles"] = [self.sample_roles_raw[4]]
        profile = {"organisation_number": self.sample_org, "evidence": {"roles": ev}}
        result = emit_roles_metrics(profile)
        self.assertIsNotNone(result["auditors"])
        self.assertEqual(len(result["auditors"]), 1)
        self.assertEqual(result["auditors"][0]["name"], "REVISJON NORGE AS")
        self.assertEqual(result["auditors"][0]["holder_organisation_number"], "987654321")

        # Absent
        ev_no_revi = copy.deepcopy(self.sample_evidence)
        ev_no_revi["value"]["roles"] = [self.sample_roles_raw[0]]
        profile_no = {"organisation_number": self.sample_org, "evidence": {"roles": ev_no_revi}}
        res_no = emit_roles_metrics(profile_no)
        self.assertIsNone(res_no["auditors"])

    # 6. Accountant/REGN emission
    def test_accountant_regn_emission(self) -> None:
        """Test authorized accountant REGN emission with normalized corporate name, and None when absent."""
        ev = copy.deepcopy(self.sample_evidence)
        ev["value"]["roles"] = [self.sample_roles_raw[5]]
        profile = {"organisation_number": self.sample_org, "evidence": {"roles": ev}}
        result = emit_roles_metrics(profile)
        self.assertIsNotNone(result["authorized_accountants"])
        self.assertEqual(len(result["authorized_accountants"]), 1)
        self.assertEqual(result["authorized_accountants"][0]["name"], "ØKONOMI SOGN AS")
        self.assertEqual(result["authorized_accountants"][0]["holder_organisation_number"], "979947143")

        # Absent
        ev_no_regn = copy.deepcopy(self.sample_evidence)
        ev_no_regn["value"]["roles"] = [self.sample_roles_raw[0]]
        profile_no = {"organisation_number": self.sample_org, "evidence": {"roles": ev_no_regn}}
        res_no = emit_roles_metrics(profile_no)
        self.assertIsNone(res_no["authorized_accountants"])

    # 7. Deputy board member/VARA emission
    def test_deputy_board_member_vara_emission(self) -> None:
        """Test deputy board member VARA emission, and None when absent."""
        ev = copy.deepcopy(self.sample_evidence)
        ev["value"]["roles"] = [self.sample_roles_raw[3]]
        profile = {"organisation_number": self.sample_org, "evidence": {"roles": ev}}
        result = emit_roles_metrics(profile)
        self.assertIsNotNone(result["deputy_board_members"])
        self.assertEqual(len(result["deputy_board_members"]), 1)
        self.assertEqual(result["deputy_board_members"][0]["name"], "Ola Varamedlem")

        # Absent
        ev_no_vara = copy.deepcopy(self.sample_evidence)
        ev_no_vara["value"]["roles"] = [self.sample_roles_raw[0]]
        profile_no = {"organisation_number": self.sample_org, "evidence": {"roles": ev_no_vara}}
        res_no = emit_roles_metrics(profile_no)
        self.assertIsNone(res_no["deputy_board_members"])

    # 8. Appointment/change-date preservation
    def test_appointment_change_date_preservation(self) -> None:
        """Test that last_changed and appointment_date are accurately preserved on each role record."""
        role_with_dates = copy.deepcopy(self.sample_roles_raw[0])
        role_with_dates["last_changed"] = "2024-09-09"
        role_with_dates["appointment_date"] = "2020-01-15"

        ev = copy.deepcopy(self.sample_evidence)
        ev["value"]["roles"] = [role_with_dates]
        profile = {"organisation_number": self.sample_org, "evidence": {"roles": ev}}
        result = emit_roles_metrics(profile)

        role = result["roles"][0]
        self.assertEqual(role["last_changed"], "2024-09-09")
        self.assertEqual(role["appointment_date"], "2020-01-15")

    # 9. Missing role evidence
    def test_missing_role_evidence(self) -> None:
        """Test handling when role evidence is missing, source_error, not_found, or not_fetched."""
        for status in ["not_found", "source_error", "not_fetched"]:
            profile = {
                "organisation_number": self.sample_org,
                "evidence": {
                    "roles": {
                        "field": "roles",
                        "status": status,
                        "value": None,
                    }
                },
            }
            res = emit_roles_metrics(profile)
            self.assertIsNone(res["roles"])
            self.assertIsNone(res["board_chair"])
            self.assertIsNone(res["managing_director"])
            self.assertIsNone(res["board_members"])
            self.assertIsNone(res["deputy_board_members"])
            self.assertIsNone(res["auditors"])
            self.assertIsNone(res["authorized_accountants"])

        # Completely absent evidence
        empty_profile = {"organisation_number": self.sample_org}
        res_empty = emit_roles_metrics(empty_profile)
        self.assertIsNone(res_empty["roles"])
        self.assertIsNone(res_empty["managing_director"])

        # Empty roles list in value
        ev_empty_list = copy.deepcopy(self.sample_evidence)
        ev_empty_list["value"]["roles"] = []
        res_empty_list = emit_roles_metrics({"organisation_number": self.sample_org, "evidence": {"roles": ev_empty_list}})
        self.assertIsNone(res_empty_list["roles"])
        self.assertIsNone(res_empty_list["board_chair"])

    # 10. Organisation-number mismatch rejection
    def test_organisation_number_mismatch_rejection(self) -> None:
        """Test strict rejection when role evidence does not match profile organisation number."""
        different_org = "123456789"

        # Mismatched source_url
        mismatched_url_ev = copy.deepcopy(self.sample_evidence)
        mismatched_url_ev["source_url"] = f"https://data.brreg.no/enhetsregisteret/api/enheter/{different_org}/roller"
        profile_url = {
            "organisation_number": self.sample_org,
            "evidence": {"roles": mismatched_url_ev},
        }
        with self.assertRaises(ValueError) as ctx:
            emit_roles_metrics(profile_url)
        self.assertIn("Roles evidence entity mismatch", str(ctx.exception))

        # Mismatched source_row_key
        mismatched_key_ev = copy.deepcopy(self.sample_evidence)
        mismatched_key_ev["source_row_key"] = different_org
        profile_key = {
            "organisation_number": self.sample_org,
            "evidence": {"roles": mismatched_key_ev},
        }
        with self.assertRaises(ValueError) as ctx:
            emit_roles_metrics(profile_key)
        self.assertIn("Roles evidence entity mismatch", str(ctx.exception))

        # Mismatched company_organisation_number in record
        mismatched_record = copy.deepcopy(self.sample_roles_raw[0])
        mismatched_record["company_organisation_number"] = different_org
        ev_record_mismatch = copy.deepcopy(self.sample_evidence)
        ev_record_mismatch["value"]["roles"] = [mismatched_record]
        profile_rec = {
            "organisation_number": self.sample_org,
            "evidence": {"roles": ev_record_mismatch},
        }
        with self.assertRaises(ValueError) as ctx:
            emit_roles_metrics(profile_rec)
        self.assertIn("Role record company_organisation_number mismatch", str(ctx.exception))

    # 11. Source metadata preservation
    def test_source_metadata_preservation(self) -> None:
        """Test that source_url, source_type, retrieved_at, and content_sha256 are strictly preserved."""
        profile = {
            "organisation_number": self.sample_org,
            "evidence": {"roles": copy.deepcopy(self.sample_evidence)},
        }
        result = emit_roles_metrics(profile)

        for role in result["roles"]:
            self.assertEqual(role["source_url"], self.sample_evidence["source_url"])
            self.assertEqual(role["source_type"], self.sample_evidence["source_type"])
            self.assertEqual(role["retrieved_at"], self.sample_evidence["retrieved_at"])
            self.assertEqual(role["content_sha256"], self.sample_evidence["content_sha256"])

    # 12. Deterministic output
    def test_deterministic_output(self) -> None:
        """Test that repeated calls produce identical, deterministic results and function is idempotent."""
        profile = {
            "organisation_number": self.sample_org,
            "evidence": {"roles": copy.deepcopy(self.sample_evidence)},
        }
        res1 = emit_roles_metrics(copy.deepcopy(profile))
        res2 = emit_roles_metrics(copy.deepcopy(profile))
        self.assertEqual(res1, res2)

        # Idempotence
        res3 = emit_roles_metrics(res1)
        self.assertEqual(res1, res3)

    # 13. Original evidence unchanged
    def test_original_evidence_unchanged(self) -> None:
        """Test that original evidence dictionary and its contents are never mutated or destroyed."""
        original_evidence = copy.deepcopy(self.sample_evidence)
        profile = {
            "organisation_number": self.sample_org,
            "evidence": {"roles": copy.deepcopy(self.sample_evidence)},
        }
        result = emit_roles_metrics(profile)
        self.assertEqual(result["evidence"]["roles"], original_evidence)

    # 14. Zero network requests
    def test_zero_network_requests(self) -> None:
        """Test that roles emission strictly executes in-memory with zero network calls."""
        profile = {
            "organisation_number": self.sample_org,
            "evidence": {"roles": copy.deepcopy(self.sample_evidence)},
        }
        with patch("socket.socket") as mock_socket:
            mock_socket.side_effect = AssertionError("Network call attempted during roles emission!")
            result = emit_roles_metrics(profile)
            self.assertIsNotNone(result["roles"])
            self.assertEqual(len(result["roles"]), 6)
            mock_socket.assert_not_called()


if __name__ == "__main__":
    unittest.main()
