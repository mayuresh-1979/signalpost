from __future__ import annotations

import re
from typing import Any


def extract_financial_record(
    record: dict[str, Any],
    profile_org: str,
    *,
    source_url: str | None = None,
    source_type: str | None = None,
    retrieved_at: str | None = None,
    content_sha256: str | None = None,
) -> dict[str, Any]:
    """Transform a single retained financial record into an entity-anchored, structured record.

    Preserves exact numeric values without calculating or inferring missing metrics.
    Leaves missing metrics as None.
    """
    period = record.get("period")
    period_from = None
    period_to = None
    if isinstance(period, dict):
        period_from = period.get("fraDato")
        period_to = period.get("tilDato")

    return {
        "organisation_number": profile_org,
        "record_id": record.get("record_id"),
        "account_type": record.get("account_type"),
        "currency": record.get("currency"),
        "reporting_period_from": period_from,
        "reporting_period_to": period_to,
        "revenue": record.get("revenue"),
        "operating_result": record.get("operating_result"),
        "profit_before_tax": record.get("profit_before_tax"),
        "annual_result": record.get("annual_result"),
        "assets": record.get("assets"),
        "equity": record.get("equity"),
        "debt": record.get("debt"),
        "source_url": source_url,
        "source_type": source_type,
        "retrieved_at": retrieved_at,
        "content_sha256": content_sha256,
    }


def emit_financial_metrics(profile: dict[str, Any]) -> dict[str, Any]:
    """Deterministically propagate retained financial evidence into structured profile fields.

    Entity Safety:
    - Verifies organisation_number matches profile.
    - If financial evidence source_url or source_row_key contains an org number, it must match profile org.
    - If evidence is missing, status != 'available', or records are empty, sets missing financial fields to None.
    - Preserves all original evidence unchanged.
    """
    profile_org = str(profile.get("organisation_number") or "").strip()
    if not profile_org:
        raise ValueError("Profile is missing organisation_number")

    fin_evidence = (profile.get("evidence") or {}).get("financials")
    if not fin_evidence or not isinstance(fin_evidence, dict) or fin_evidence.get("status") != "available":
        profile["financials"] = None
        profile["revenue"] = None
        profile["operating_result"] = None
        profile["profit_before_tax"] = None
        profile["annual_result"] = None
        profile["assets"] = None
        profile["equity"] = None
        profile["debt"] = None
        profile["currency"] = None
        profile["reporting_period_from"] = None
        profile["reporting_period_to"] = None
        return profile

    source_url = fin_evidence.get("source_url")
    source_type = fin_evidence.get("source_type")
    retrieved_at = fin_evidence.get("retrieved_at")
    content_sha256 = fin_evidence.get("content_sha256")
    source_row_key = fin_evidence.get("source_row_key")

    # Strict Entity Safety Check 1: source_row_key check
    if source_row_key and str(source_row_key).strip() != profile_org:
        raise ValueError(
            f"Financial evidence entity mismatch: source_row_key {source_row_key!r} "
            f"!= profile organisation_number {profile_org!r}"
        )

    # Strict Entity Safety Check 2: source_url check (if URL contains /regnskap/{org})
    if source_url:
        match = re.search(r"/regnskap/(\d{9})\b", source_url)
        if match and match.group(1) != profile_org:
            raise ValueError(
                f"Financial evidence entity mismatch: source_url org {match.group(1)!r} "
                f"!= profile organisation_number {profile_org!r}"
            )

    records_raw = (fin_evidence.get("value") or {}).get("records")
    if not records_raw or not isinstance(records_raw, list):
        profile["financials"] = None
        profile["revenue"] = None
        profile["operating_result"] = None
        profile["profit_before_tax"] = None
        profile["annual_result"] = None
        profile["assets"] = None
        profile["equity"] = None
        profile["debt"] = None
        profile["currency"] = None
        profile["reporting_period_from"] = None
        profile["reporting_period_to"] = None
        return profile

    emitted_records = [
        extract_financial_record(
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
        profile["financials"] = None
        profile["revenue"] = None
        profile["operating_result"] = None
        profile["profit_before_tax"] = None
        profile["annual_result"] = None
        profile["assets"] = None
        profile["equity"] = None
        profile["debt"] = None
        profile["currency"] = None
        profile["reporting_period_from"] = None
        profile["reporting_period_to"] = None
        return profile

    latest = emitted_records[0]

    profile["financials"] = {
        "status": "available",
        "organisation_number": profile_org,
        "currency": latest["currency"],
        "reporting_period_from": latest["reporting_period_from"],
        "reporting_period_to": latest["reporting_period_to"],
        "revenue": latest["revenue"],
        "operating_result": latest["operating_result"],
        "profit_before_tax": latest["profit_before_tax"],
        "annual_result": latest["annual_result"],
        "assets": latest["assets"],
        "equity": latest["equity"],
        "debt": latest["debt"],
        "records": emitted_records,
        "source_url": source_url,
        "source_type": source_type,
        "retrieved_at": retrieved_at,
        "content_sha256": content_sha256,
    }

    # Top-level profile convenience fields:
    profile["revenue"] = latest["revenue"]
    profile["operating_result"] = latest["operating_result"]
    profile["profit_before_tax"] = latest["profit_before_tax"]
    profile["annual_result"] = latest["annual_result"]
    profile["assets"] = latest["assets"]
    profile["equity"] = latest["equity"]
    profile["debt"] = latest["debt"]
    profile["currency"] = latest["currency"]
    profile["reporting_period_from"] = latest["reporting_period_from"]
    profile["reporting_period_to"] = latest["reporting_period_to"]

    return profile
