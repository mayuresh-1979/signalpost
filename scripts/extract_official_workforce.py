#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.external_footprint import (  # noqa: E402
    publishable_observation,
    validate_observation,
)


def extract_entity_workforce(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Extract authoritative legal-entity workforce observation from official BRREG registry evidence."""
    org = str(profile.get("organisation_number") or "").strip()
    if not org.isdigit():
        return None

    name = str(profile.get("name") or "").strip() or org
    evidence_dict = profile.get("evidence") or {}

    # Check registry_live first, then fallback to bulk registry evidence
    reg_ev = evidence_dict.get("registry_live") or {}
    reg_val = reg_ev.get("value") or {} if reg_ev.get("status") == "available" else {}
    emp_val = reg_val.get("employees") if reg_val.get("employees") is not None else reg_val.get("antallAnsatte")

    if emp_val is None or str(emp_val).strip() == "" or not str(emp_val).strip().isdigit():
        reg_ev = evidence_dict.get("registry") or {}
        reg_val = reg_ev.get("value") or {} if reg_ev.get("status") == "available" else {}
        emp_val = reg_val.get("employees") if reg_val.get("employees") is not None else reg_val.get("antallAnsatte")

    if reg_ev.get("status") != "available" or emp_val is None:
        return None

    ansatte_raw = str(emp_val).strip()
    if not ansatte_raw.isdigit():
        return None

    ansatte = int(ansatte_raw)
    digest = str(reg_ev.get("content_sha256") or "").strip()
    if len(digest) != 64:
        return None

    retrieved_at = str(reg_ev.get("retrieved_at") or "").strip()
    if not retrieved_at:
        return None

    source_url = f"https://data.brreg.no/enhetsregisteret/api/enheter/{org}"
    obs_id = f"brreg-workforce-entity-{org}-{digest[:16]}"
    bulk_val = (evidence_dict.get("registry") or {}).get("value") or {}
    effective_at = (
        reg_ev.get("effective_at")
        or reg_ev.get("as_of")
        or reg_val.get("registreringsdatoAntallAnsatteEnhetsregisteret")
        or bulk_val.get("registreringsdatoAntallAnsatteEnhetsregisteret")
    )

    observation = {
        "id": obs_id,
        "organisation_number": org,
        "platform": "brreg",
        "signal_type": "workforce_snapshot",
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "content_sha256": digest,
        "exact_entity": True,
        "identity_proof": [
            {
                "type": "official_brreg_registry_anchor",
                "organisation_number": org,
                "legal_name": name,
            }
        ],
        "acquisition_mode": "official_api",
        "rights_status": "approved",
        "source_class": "official_company_registry",
        "evidence_span": f"Official Enhetsregisteret entry reports {ansatte} registered employees for {name} ({org}).",
        "effective_at": str(effective_at) if effective_at else None,
        "metrics": {
            "employees": ansatte,
            "workforce_scope": "legal_entity",
            "reporting_source": "enhetsregisteret",
            "reporting_date": str(effective_at) if effective_at else None,
            "interpretation": "Official Norwegian register employee count; not independent employee sentiment.",
        },
        "strategy": "registry_workforce_snapshot",
    }

    if not publishable_observation(observation):
        return None

    return observation


def extract_subunit_workforce(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract authoritative establishment-level workforce observations from official BRREG subunit evidence."""
    org = str(profile.get("organisation_number") or "").strip()
    if not org.isdigit():
        return []

    name = str(profile.get("name") or "").strip() or org
    loc_ev = (profile.get("evidence") or {}).get("locations") or {}
    if loc_ev.get("status") != "available":
        return []

    digest = str(loc_ev.get("content_sha256") or "").strip()
    if len(digest) != 64:
        return []

    retrieved_at = str(loc_ev.get("retrieved_at") or "").strip()
    if not retrieved_at:
        return []

    locations = (loc_ev.get("value") or {}).get("locations") or []
    effective_at = loc_ev.get("effective_at") or loc_ev.get("as_of")
    results = []

    for loc in locations:
        sub_emp = loc.get("employees")
        if sub_emp is None:
            continue
        sub_emp_str = str(sub_emp).strip()
        if not sub_emp_str.isdigit():
            continue

        sub_emp_int = int(sub_emp_str)
        sub_org = str(loc.get("organisation_number") or "").strip()
        if not sub_org.isdigit():
            continue

        sub_name = str(loc.get("name") or "").strip() or sub_org
        source_url = f"https://data.brreg.no/enhetsregisteret/api/underenheter/{sub_org}"
        obs_id = f"brreg-workforce-subunit-{org}-{sub_org}-{digest[:16]}"

        obs = {
            "id": obs_id,
            "organisation_number": org,
            "platform": "brreg",
            "signal_type": "workforce_snapshot",
            "source_url": source_url,
            "retrieved_at": retrieved_at,
            "content_sha256": digest,
            "exact_entity": True,
            "identity_proof": [
                {
                    "type": "official_registered_subunit",
                    "parent_organisation_number": org,
                    "subunit_organisation_number": sub_org,
                    "subunit_name": sub_name,
                }
            ],
            "acquisition_mode": "official_api",
            "rights_status": "approved",
            "source_class": "official_subunit_registry",
            "evidence_span": f"Official Underenhetsregisteret entry reports {sub_emp_int} employees for subunit {sub_name} ({sub_org}) under parent {name} ({org}).",
            "effective_at": str(effective_at) if effective_at else None,
            "metrics": {
                "employees": sub_emp_int,
                "workforce_scope": "subunit",
                "subunit_organisation_number": sub_org,
                "subunit_name": sub_name,
                "reporting_source": "underenheter",
                "interpretation": "Official Norwegian subunit workplace employee count; not independent employee sentiment.",
            },
            "strategy": "registry_workforce_snapshot",
        }

        if publishable_observation(obs):
            results.append(obs)

    return results


def extract_workforce_observations(
    profile: dict[str, Any],
    scope: str = "all",
) -> list[dict[str, Any]]:
    """Extract workforce observations for a company profile based on requested scope ('all', 'registry', 'subunits')."""
    observations: list[dict[str, Any]] = []

    if scope in ("all", "registry"):
        entity_obs = extract_entity_workforce(profile)
        if entity_obs is not None:
            observations.append(entity_obs)

    if scope in ("all", "subunits"):
        sub_obs = extract_subunit_workforce(profile)
        observations.extend(sub_obs)

    return observations


def observation(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Backward-compatible helper returning the primary entity workforce observation if available, else first subunit."""
    obs_list = extract_workforce_observations(profile, scope="all")
    return obs_list[0] if obs_list else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract authoritative workforce observations from BRREG registry and subunit evidence."
    )
    parser.add_argument("--profiles", required=True, help="Input profiles JSONL file")
    parser.add_argument("--output", required=True, help="Output observations JSONL file")
    parser.add_argument("--report", required=True, help="Output report JSON file")
    parser.add_argument(
        "--scope",
        choices=["all", "registry", "subunits"],
        default="all",
        help="Scope of workforce observations to extract (default: all)",
    )
    args = parser.parse_args()

    profiles_path = Path(args.profiles)
    profiles = [
        json.loads(line)
        for line in profiles_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    all_observations: list[dict[str, Any]] = []
    companies_with_workforce: set[str] = set()
    entity_count = 0
    subunit_count = 0

    for profile in profiles:
        obs = extract_workforce_observations(profile, scope=args.scope)
        if obs:
            companies_with_workforce.add(str(profile.get("organisation_number")))
            for item in obs:
                scope = (item.get("metrics") or {}).get("workforce_scope")
                if scope == "legal_entity":
                    entity_count += 1
                elif scope == "subunit":
                    subunit_count += 1
            all_observations.extend(obs)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for item in all_observations:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    report = {
        "connector": "official_brreg_workforce_v1",
        "scope": args.scope,
        "profiles": len(profiles),
        "companies_with_workforce": len(companies_with_workforce),
        "total_observations": len(all_observations),
        "entity_observations": entity_count,
        "subunit_observations": subunit_count,
        "source": "Brønnøysund Enhetsregisteret & Underenheter (NLOD 2.0)",
        "claim_boundary": "Official Norwegian register employee counts; never treated as independent sentiment or self-reported headcount.",
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
