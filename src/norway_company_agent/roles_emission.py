from __future__ import annotations

import re
from typing import Any


def extract_role_record(
    record: dict[str, Any],
    profile_org: str,
    *,
    source_url: str | None = None,
    source_type: str | None = None,
    retrieved_at: str | None = None,
    content_sha256: str | None = None,
) -> dict[str, Any]:
    """Transform a single retained role record into an entity-anchored, structured record.

    Preserves exact role metadata without inventing personal details or roles.
    Anchors organisation_number to profile_org.
    """
    if "company_organisation_number" in record and record["company_organisation_number"] != profile_org:
        raise ValueError(
            f"Role record company_organisation_number mismatch: "
            f"{record['company_organisation_number']!r} != {profile_org!r}"
        )

    raw_name = record.get("name")
    if isinstance(raw_name, list):
        formatted_name = " ".join(str(part).strip() for part in raw_name if str(part).strip()) or None
    elif isinstance(raw_name, str):
        formatted_name = raw_name.strip() or None
    else:
        formatted_name = None

    return {
        "organisation_number": profile_org,
        "company_organisation_number": profile_org,
        "holder_organisation_number": record.get("organisation_number"),
        "name": formatted_name,
        "raw_name": raw_name,
        "role_code": record.get("role_code"),
        "role": record.get("role"),
        "group_code": record.get("group_code"),
        "group": record.get("group"),
        "appointment_date": record.get("appointment_date"),
        "last_changed": record.get("last_changed"),
        "inactive": bool(record.get("inactive", False)),
        "source_url": source_url,
        "source_type": source_type,
        "retrieved_at": retrieved_at,
        "content_sha256": content_sha256,
    }


def emit_roles_metrics(profile: dict[str, Any]) -> dict[str, Any]:
    """Deterministically propagate retained official role evidence into structured profile fields.

    Entity Safety:
    - Verifies organisation_number matches profile.
    - If role evidence source_url or source_row_key contains an org number, it must match profile org.
    - If evidence is missing, status != 'available', or records are empty, sets role fields to None.
    - Preserves all original evidence unchanged.
    """
    profile_org = str(profile.get("organisation_number") or "").strip()
    if not profile_org:
        raise ValueError("Profile is missing organisation_number")

    roles_evidence = (profile.get("evidence") or {}).get("roles")
    if (
        not roles_evidence
        or not isinstance(roles_evidence, dict)
        or roles_evidence.get("status") != "available"
    ):
        profile["roles"] = None
        profile["board_chair"] = None
        profile["managing_director"] = None
        profile["board_members"] = None
        profile["deputy_board_members"] = None
        profile["auditors"] = None
        profile["authorized_accountants"] = None
        return profile

    source_url = roles_evidence.get("source_url")
    source_type = roles_evidence.get("source_type")
    retrieved_at = roles_evidence.get("retrieved_at")
    content_sha256 = roles_evidence.get("content_sha256")
    source_row_key = roles_evidence.get("source_row_key")

    # Strict Entity Safety Check 1: source_row_key check
    if source_row_key and str(source_row_key).strip() != profile_org:
        raise ValueError(
            f"Roles evidence entity mismatch: source_row_key {source_row_key!r} "
            f"!= profile organisation_number {profile_org!r}"
        )

    # Strict Entity Safety Check 2: source_url check (if URL contains /api/enheter/{org} or /enheter/{org})
    if source_url:
        match = re.search(r"/enheter/(\d{9})\b", source_url)
        if match and match.group(1) != profile_org:
            raise ValueError(
                f"Roles evidence entity mismatch: source_url org {match.group(1)!r} "
                f"!= profile organisation_number {profile_org!r}"
            )

    records_raw = (roles_evidence.get("value") or {}).get("roles")
    if not records_raw or not isinstance(records_raw, list):
        profile["roles"] = None
        profile["board_chair"] = None
        profile["managing_director"] = None
        profile["board_members"] = None
        profile["deputy_board_members"] = None
        profile["auditors"] = None
        profile["authorized_accountants"] = None
        return profile

    emitted_records = [
        extract_role_record(
            rec,
            profile_org,
            source_url=source_url,
            source_type=source_type,
            retrieved_at=retrieved_at,
            content_sha256=content_sha256,
        )
        for rec in records_raw
        if isinstance(rec, dict)
    ]

    if not emitted_records:
        profile["roles"] = None
        profile["board_chair"] = None
        profile["managing_director"] = None
        profile["board_members"] = None
        profile["deputy_board_members"] = None
        profile["auditors"] = None
        profile["authorized_accountants"] = None
        return profile

    profile["roles"] = emitted_records

    # Board chair (LEDE) - prefer active if multiple, else first
    ledes = [r for r in emitted_records if r.get("role_code") == "LEDE"]
    active_ledes = [r for r in ledes if not r.get("inactive")]
    profile["board_chair"] = active_ledes[0] if active_ledes else (ledes[0] if ledes else None)

    # Managing director / CEO (DAGL) - prefer active if multiple, else first
    dagls = [r for r in emitted_records if r.get("role_code") == "DAGL"]
    active_dagls = [r for r in dagls if not r.get("inactive")]
    profile["managing_director"] = active_dagls[0] if active_dagls else (dagls[0] if dagls else None)

    # Plural lists
    medls = [r for r in emitted_records if r.get("role_code") == "MEDL"]
    profile["board_members"] = medls if medls else None

    varas = [r for r in emitted_records if r.get("role_code") == "VARA"]
    profile["deputy_board_members"] = varas if varas else None

    revis = [r for r in emitted_records if r.get("role_code") == "REVI"]
    profile["auditors"] = revis if revis else None

    regns = [r for r in emitted_records if r.get("role_code") == "REGN"]
    profile["authorized_accountants"] = regns if regns else None

    return profile
