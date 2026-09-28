from __future__ import annotations

import re
from datetime import date
from typing import Any

from .contact_registration_emission import (
    _verify_registry_bulk_entity,
    get_safe_bulk_field,
    is_csv_quote_shifted,
)

PURPOSE_ACTIVITY_FIELD_KEYS = (
    "statutory_purpose",
    "operational_activity",
)

VAT_FIELD_KEYS = (
    "registered",
    "registered_date",
    "enhetsregisteret_registered_date",
    "voluntary_descriptions",
    "voluntary_registered_date",
)

AUDIT_FIELD_KEYS = (
    "exemption_date",
    "decision_date",
)

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PURE_NUMERIC_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def _validate_iso_date(value: Any) -> str | None:
    """Validate a strict YYYY-MM-DD calendar date."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not _ISO_DATE_RE.match(cleaned):
        return None
    try:
        date.fromisoformat(cleaned)
    except ValueError:
        return None
    return cleaned


def _validate_boolean(value: Any) -> bool | None:
    """Validate an explicit boolean or 'true'/'false' string without inferring from missing values."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned == "true":
            return True
        if cleaned == "false":
            return False
    return None


def _validate_purpose_or_activity_text(value: Any) -> str | None:
    """Validate official BRREG purpose/activity text while preserving exact retained wording."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.lower() in {"null", "true", "false", "nok"}:
        return None
    if _ISO_DATE_RE.match(stripped) or _PURE_NUMERIC_RE.match(stripped):
        return None
    return value


def _validate_voluntary_mva_description(value: Any) -> str | None:
    """Validate an explicit voluntary MVA registration description string."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.lower() in {"null", "true", "false", "nok"}:
        return None
    if _ISO_DATE_RE.match(stripped) or _PURE_NUMERIC_RE.match(stripped):
        return None
    return stripped


def extract_purpose_activity_record(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Extract an entity-anchored, CSV-shift-safe purpose and operational activity record.

    Sources:
    - evidence.registry.value.vedtektsfestetFormaal (col 64)
    - evidence.registry.value.aktivitet (col 65)

    Returns None when:
    - evidence.registry is missing or not 'available'
    - the bulk registry row exhibits the CSV quote-shift corruption signature
    - both statutory_purpose and operational_activity are absent
    """
    profile_org = str(profile.get("organisation_number") or "").strip()
    if not profile_org:
        raise ValueError("Profile is missing organisation_number")

    reg_bulk_ev = (profile.get("evidence") or {}).get("registry") or {}
    val = _verify_registry_bulk_entity(profile_org, reg_bulk_ev)
    if val is None:
        return None

    # Critical CSV-shift safety guard: columns 64 (vedtektsfestetFormaal) and 65 (aktivitet)
    # are the exact origin of the bulk CSV quote-shift corruption and must never be emitted on shifted rows.
    if is_csv_quote_shifted(val):
        return None

    statutory_purpose = _validate_purpose_or_activity_text(
        get_safe_bulk_field(val, "vedtektsfestetFormaal")
    )
    operational_activity = _validate_purpose_or_activity_text(
        get_safe_bulk_field(val, "aktivitet")
    )

    if statutory_purpose is None and operational_activity is None:
        return None

    return {
        "organisation_number": profile_org,
        "statutory_purpose": statutory_purpose,
        "operational_activity": operational_activity,
        "source_url": reg_bulk_ev.get("source_url"),
        "source_type": reg_bulk_ev.get("source_type"),
        "source_class": reg_bulk_ev.get("source_class") or reg_bulk_ev.get("source_type"),
        "retrieved_at": reg_bulk_ev.get("retrieved_at"),
        "effective_at": reg_bulk_ev.get("effective_at") or reg_bulk_ev.get("as_of"),
        "content_sha256": reg_bulk_ev.get("content_sha256"),
    }


def extract_vat_record(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Extract an entity-anchored MVA/VAT registration metadata record from evidence.registry.value.

    Sources (columns 39–43 in brreg-enheter.csv, preceding the column 64 quote-shift boundary):
    - registrertIMvaRegisteret (col 39)
    - registreringsdatoMerverdiavgiftsregisteret (col 40)
    - registreringsdatoMerverdiavgiftsregisteretEnhetsregisteret (col 41)
    - frivilligMvaRegistrertBeskrivelser (col 42)
    - registreringsdatoFrivilligMerverdiavgiftsregisteret (col 43)

    Preserves each MVA field separately without inferring booleans or dates from missing values.
    """
    profile_org = str(profile.get("organisation_number") or "").strip()
    if not profile_org:
        raise ValueError("Profile is missing organisation_number")

    reg_bulk_ev = (profile.get("evidence") or {}).get("registry") or {}
    val = _verify_registry_bulk_entity(profile_org, reg_bulk_ev)
    if val is None:
        return None

    registered = _validate_boolean(get_safe_bulk_field(val, "registrertIMvaRegisteret"))
    registered_date = _validate_iso_date(
        get_safe_bulk_field(val, "registreringsdatoMerverdiavgiftsregisteret")
    )
    enhetsregisteret_registered_date = _validate_iso_date(
        get_safe_bulk_field(
            val, "registreringsdatoMerverdiavgiftsregisteretEnhetsregisteret"
        )
    )
    voluntary_descriptions = _validate_voluntary_mva_description(
        get_safe_bulk_field(val, "frivilligMvaRegistrertBeskrivelser")
    )
    voluntary_registered_date = _validate_iso_date(
        get_safe_bulk_field(val, "registreringsdatoFrivilligMerverdiavgiftsregisteret")
    )

    if all(
        field_val is None
        for field_val in (
            registered,
            registered_date,
            enhetsregisteret_registered_date,
            voluntary_descriptions,
            voluntary_registered_date,
        )
    ):
        return None

    return {
        "organisation_number": profile_org,
        "registered": registered,
        "registered_date": registered_date,
        "enhetsregisteret_registered_date": enhetsregisteret_registered_date,
        "voluntary_descriptions": voluntary_descriptions,
        "voluntary_registered_date": voluntary_registered_date,
        "source_url": reg_bulk_ev.get("source_url"),
        "source_type": reg_bulk_ev.get("source_type"),
        "source_class": reg_bulk_ev.get("source_class") or reg_bulk_ev.get("source_type"),
        "retrieved_at": reg_bulk_ev.get("retrieved_at"),
        "effective_at": reg_bulk_ev.get("effective_at") or reg_bulk_ev.get("as_of"),
        "content_sha256": reg_bulk_ev.get("content_sha256"),
    }


def extract_audit_record(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Extract an entity-anchored, CSV-shift-safe audit exemption metadata record.

    Sources (columns 69–70 in brreg-enheter.csv):
    - fravalgRevisjonDato (col 69)
    - fravalgRevisjonBeslutningsDato (col 70)

    Never infers audit exemption status from legal form, absence of an auditor role, or missing dates.
    """
    profile_org = str(profile.get("organisation_number") or "").strip()
    if not profile_org:
        raise ValueError("Profile is missing organisation_number")

    reg_bulk_ev = (profile.get("evidence") or {}).get("registry") or {}
    val = _verify_registry_bulk_entity(profile_org, reg_bulk_ev)
    if val is None:
        return None

    # Critical CSV-shift safety guard: columns 69–70 are >= 64 and shifted on corrupted rows.
    if is_csv_quote_shifted(val):
        return None

    exemption_date = _validate_iso_date(get_safe_bulk_field(val, "fravalgRevisjonDato"))
    decision_date = _validate_iso_date(
        get_safe_bulk_field(val, "fravalgRevisjonBeslutningsDato")
    )

    if exemption_date is None and decision_date is None:
        return None

    return {
        "organisation_number": profile_org,
        "exemption_date": exemption_date,
        "decision_date": decision_date,
        "source_url": reg_bulk_ev.get("source_url"),
        "source_type": reg_bulk_ev.get("source_type"),
        "source_class": reg_bulk_ev.get("source_class") or reg_bulk_ev.get("source_type"),
        "retrieved_at": reg_bulk_ev.get("retrieved_at"),
        "effective_at": reg_bulk_ev.get("effective_at") or reg_bulk_ev.get("as_of"),
        "content_sha256": reg_bulk_ev.get("content_sha256"),
    }


def emit_purpose_vat_audit_metrics(profile: dict[str, Any]) -> dict[str, Any]:
    """Deterministically propagate retained BRREG statutory purpose, operational activity, MVA/VAT, and audit metadata.

    Populates:
    - profile["purpose_activity"], profile["statutory_purpose"], profile["operational_activity"]
    - profile["vat"], profile["vat_registered"], profile["vat_registered_date"],
      profile["vat_enhetsregisteret_registered_date"], profile["vat_voluntary_descriptions"],
      profile["vat_voluntary_registered_date"]
    - profile["audit"], profile["audit_exemption_date"], profile["audit_decision_date"]

    Preserves profile["evidence"] and all Phase 18–22 fields unchanged.
    """
    purpose_rec = extract_purpose_activity_record(profile)
    if purpose_rec is None:
        profile["purpose_activity"] = None
        profile["statutory_purpose"] = None
        profile["operational_activity"] = None
    else:
        profile["purpose_activity"] = purpose_rec
        profile["statutory_purpose"] = purpose_rec["statutory_purpose"]
        profile["operational_activity"] = purpose_rec["operational_activity"]

    vat_rec = extract_vat_record(profile)
    if vat_rec is None:
        profile["vat"] = None
        profile["vat_registered"] = None
        profile["vat_registered_date"] = None
        profile["vat_enhetsregisteret_registered_date"] = None
        profile["vat_voluntary_descriptions"] = None
        profile["vat_voluntary_registered_date"] = None
    else:
        profile["vat"] = vat_rec
        profile["vat_registered"] = vat_rec["registered"]
        profile["vat_registered_date"] = vat_rec["registered_date"]
        profile["vat_enhetsregisteret_registered_date"] = vat_rec[
            "enhetsregisteret_registered_date"
        ]
        profile["vat_voluntary_descriptions"] = vat_rec["voluntary_descriptions"]
        profile["vat_voluntary_registered_date"] = vat_rec["voluntary_registered_date"]

    audit_rec = extract_audit_record(profile)
    if audit_rec is None:
        profile["audit"] = None
        profile["audit_exemption_date"] = None
        profile["audit_decision_date"] = None
    else:
        profile["audit"] = audit_rec
        profile["audit_exemption_date"] = audit_rec["exemption_date"]
        profile["audit_decision_date"] = audit_rec["decision_date"]

    return profile
