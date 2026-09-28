#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from norway_company_agent.external_footprint import (  # noqa: E402
    PLATFORMS,
    SIGNAL_TYPES,
    PUBLISHABLE_ACQUISITION_MODES,
    publishable_observation,
    validate_observation,
)
from scripts.extract_official_workforce import (  # noqa: E402
    extract_entity_workforce,
    extract_subunit_workforce,
    extract_workforce_observations,
    observation,
)


def _sample_profile() -> dict:
    return {
        "organisation_number": "916340257",
        "name": "WYSSEN NORGE AS",
        "evidence": {
            "registry": {
                "status": "available",
                "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv",
                "retrieved_at": "2026-09-22T13:56:52Z",
                "content_sha256": "a" * 64,
                "value": {
                    "organisasjonsnummer": "916340257",
                    "navn": "WYSSEN NORGE AS",
                    "antallAnsatte": "5",
                },
            },
            "registry_live": {
                "status": "available",
                "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/916340257",
                "retrieved_at": "2026-09-22T13:56:52Z",
                "content_sha256": "b" * 64,
                "value": {
                    "organisation_number": "916340257",
                    "name": "WYSSEN NORGE AS",
                    "employees": 5,
                },
            },
            "locations": {
                "status": "available",
                "source_url": "https://data.brreg.no/enhetsregisteret/api/underenheter/lastned/csv",
                "retrieved_at": "2026-09-22T13:57:25Z",
                "content_sha256": "c" * 64,
                "value": {
                    "locations": [
                        {
                            "organisation_number": "926826182",
                            "name": "WYSSEN NORGE AVD SOGNDAL",
                            "employees": 5,
                        },
                        {
                            "organisation_number": "926826190",
                            "name": "WYSSEN NORGE AVD OSLO",
                            "employees": 2,
                        },
                    ]
                },
            },
        },
    }


def test_valid_registry_employee_observation():
    """Verify that valid registry antallAnsatte produces a compliant observation."""
    profile = _sample_profile()
    obs = extract_entity_workforce(profile)
    assert obs is not None
    assert obs["organisation_number"] == "916340257"
    assert obs["platform"] == "brreg"
    assert obs["signal_type"] == "workforce_snapshot"
    assert obs["acquisition_mode"] == "official_api"
    assert obs["rights_status"] == "approved"
    assert obs["source_class"] == "official_company_registry"
    assert obs["exact_entity"] is True
    assert obs["metrics"]["employees"] == 5
    assert obs["metrics"]["workforce_scope"] == "legal_entity"
    assert obs["metrics"]["reporting_source"] == "enhetsregisteret"
    assert "916340257" in obs["source_url"]

    errors = validate_observation(obs)
    assert errors == [], f"Validation errors: {errors}"
    assert publishable_observation(obs) is True


def test_valid_subunit_employee_observation():
    """Verify that subunit employee counts produce compliant establishment-level observations."""
    profile = _sample_profile()
    sub_obs = extract_subunit_workforce(profile)
    assert len(sub_obs) == 2
    for item in sub_obs:
        assert item["organisation_number"] == "916340257"
        assert item["platform"] == "brreg"
        assert item["signal_type"] == "workforce_snapshot"
        assert item["acquisition_mode"] == "official_api"
        assert item["rights_status"] == "approved"
        assert item["source_class"] == "official_subunit_registry"
        assert item["exact_entity"] is True
        assert item["metrics"]["workforce_scope"] == "subunit"
        assert item["metrics"]["reporting_source"] == "underenheter"
        assert item["metrics"]["employees"] in (5, 2)
        assert item["metrics"]["subunit_organisation_number"] in ("926826182", "926826190")

        errors = validate_observation(item)
        assert errors == [], f"Validation errors: {errors}"
        assert publishable_observation(item) is True


def test_missing_employee_value_no_fabricated_observation():
    """Verify that absent or non-numeric employee counts emit zero fabricated observations."""
    profile_empty = {
        "organisation_number": "123456789",
        "name": "NO EMPLOYEES AS",
        "evidence": {
            "registry": {
                "status": "available",
                "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv",
                "retrieved_at": "2026-09-22T13:56:52Z",
                "content_sha256": "d" * 64,
                "value": {
                    "antallAnsatte": "",  # Empty string
                },
            },
            "locations": {
                "status": "available",
                "source_url": "https://data.brreg.no/enhetsregisteret/api/underenheter/lastned/csv",
                "retrieved_at": "2026-09-22T13:57:25Z",
                "content_sha256": "e" * 64,
                "value": {
                    "locations": [
                        {
                            "organisation_number": "999888777",
                            "name": "NO EMPLOYEES SUBUNIT",
                            "employees": None,  # None
                        }
                    ]
                },
            },
        },
    }
    assert extract_entity_workforce(profile_empty) is None
    assert extract_subunit_workforce(profile_empty) == []
    assert extract_workforce_observations(profile_empty) == []
    assert observation(profile_empty) is None


def test_exact_organisation_number_association():
    """Verify that both registry and subunit observations anchor on parent organisation number."""
    profile = _sample_profile()
    all_obs = extract_workforce_observations(profile, scope="all")
    assert len(all_obs) == 3
    for obs in all_obs:
        # Parent org anchor is always preserved
        assert obs["organisation_number"] == "916340257"
        assert obs["exact_entity"] is True


def test_deterministic_output():
    """Verify that repeated extraction produces byte-for-byte identical output."""
    profile = _sample_profile()
    obs1 = extract_workforce_observations(profile, scope="all")
    obs2 = extract_workforce_observations(profile, scope="all")
    assert json.dumps(obs1, sort_keys=True) == json.dumps(obs2, sort_keys=True)


def test_no_duplicate_observation_ids():
    """Verify that all observation IDs for a profile with multiple subunits are distinct."""
    profile = _sample_profile()
    all_obs = extract_workforce_observations(profile, scope="all")
    ids = [o["id"] for o in all_obs]
    assert len(ids) == len(set(ids)), f"Duplicate IDs detected: {ids}"


def test_correct_source_and_acquisition_metadata():
    """Verify platform, signal_type, acquisition_mode, rights_status, and sha256 hash validity."""
    profile = _sample_profile()
    for obs in extract_workforce_observations(profile, scope="all"):
        assert obs["platform"] in PLATFORMS
        assert obs["signal_type"] in SIGNAL_TYPES
        assert obs["acquisition_mode"] in PUBLISHABLE_ACQUISITION_MODES
        assert obs["rights_status"] == "approved"
        assert len(obs["content_sha256"]) == 64
        assert obs["source_url"].startswith("https://data.brreg.no/")


def test_refresh_replay_produces_identical_results():
    """Verify that extraction replay across multiple profile instances is idempotent."""
    profile = _sample_profile()
    obs_first = extract_workforce_observations(profile)
    # Simulate replay
    obs_second = extract_workforce_observations(profile)
    assert len(obs_first) == len(obs_second)
    for a, b in zip(obs_first, obs_second):
        assert a["id"] == b["id"]
        assert a["metrics"] == b["metrics"]
        assert a["source_url"] == b["source_url"]
        assert a["content_sha256"] == b["content_sha256"]


if __name__ == "__main__":
    test_valid_registry_employee_observation()
    test_valid_subunit_employee_observation()
    test_missing_employee_value_no_fabricated_observation()
    test_exact_organisation_number_association()
    test_deterministic_output()
    test_no_duplicate_observation_ids()
    test_correct_source_and_acquisition_metadata()
    test_refresh_replay_produces_identical_results()
    print("All 8 official workforce tests passed successfully!")
