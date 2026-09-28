from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

from .contact_registration_emission import (
    _verify_registry_bulk_entity,
    get_safe_bulk_field,
    is_csv_quote_shifted,
)

VALID_CAPITAL_TYPES = frozenset(
    {
        "Aksjekapital",
        "Grunnkapital",
        "Eierandelskapital",
        "Selskapskapital",
        "Andelskapital",
    }
)

CAPITAL_FIELD_KEYS = (
    "amount",
    "currency",
    "registered_date",
    "share_count",
    "type",
    "paid_in",
    "fully_paid_in",
    "bound",
)

_NUMERIC_AMOUNT_RE = re.compile(r"^\d+(?:\.\d+)?$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_SHARE_COUNT_RE = re.compile(r"^\d+$")


def _validate_numeric_amount(value: Any) -> float | None:
    """Validate a non-negative numeric capital amount without coercing arbitrary strings."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        if not math.isfinite(num) or num < 0.0:
            return None
        return num
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or cleaned.lower() == "null":
            return None
        if not _NUMERIC_AMOUNT_RE.match(cleaned):
            return None
        try:
            num = float(cleaned)
        except ValueError:
            return None
        if not math.isfinite(num) or num < 0.0:
            return None
        return num
    return None


def _validate_currency(value: Any) -> str | None:
    """Validate an explicit 3-letter uppercase ISO currency code without defaulting to NOK."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not _CURRENCY_RE.match(cleaned):
        return None
    return cleaned


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


def _validate_share_count(value: Any) -> int | None:
    """Validate a positive integer share count without coercing decimals or arbitrary strings."""
    if value is None or isinstance(value, bool) or isinstance(value, float):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        cleaned = value.strip()
        if not _SHARE_COUNT_RE.match(cleaned):
            return None
        try:
            count = int(cleaned)
        except ValueError:
            return None
        return count if count > 0 else None
    return None


def _validate_capital_type(value: Any) -> str | None:
    """Validate a statutory BRREG capital type without normalizing away distinctions."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if cleaned not in VALID_CAPITAL_TYPES:
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


def extract_capital_record(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Extract an entity-anchored, CSV-shift-safe structured capital record from evidence.registry.value.

    Returns None when:
    - evidence.registry is missing or not 'available'
    - the bulk registry row exhibits the CSV quote-shift corruption signature
    - no capital fields are present and valid
    """
    profile_org = str(profile.get("organisation_number") or "").strip()
    if not profile_org:
        raise ValueError("Profile is missing organisation_number")

    reg_bulk_ev = (profile.get("evidence") or {}).get("registry") or {}
    val = _verify_registry_bulk_entity(profile_org, reg_bulk_ev)
    if val is None:
        return None

    # Critical CSV-shift safety guard: never emit capital fields from quote-shifted bulk rows
    if is_csv_quote_shifted(val):
        return None

    amount = _validate_numeric_amount(get_safe_bulk_field(val, "kapital.belop"))
    currency = _validate_currency(get_safe_bulk_field(val, "kapital.valuta"))
    registered_date = _validate_iso_date(get_safe_bulk_field(val, "kapital.innfortDato"))
    share_count = _validate_share_count(get_safe_bulk_field(val, "kapital.antallAksjer"))
    capital_type = _validate_capital_type(get_safe_bulk_field(val, "kapital.type"))
    paid_in = _validate_numeric_amount(get_safe_bulk_field(val, "kapital.innbetalt"))
    fully_paid_in = _validate_boolean(get_safe_bulk_field(val, "kapital.fulltInnbetalt"))
    bound = _validate_numeric_amount(get_safe_bulk_field(val, "kapital.bundet"))

    if all(
        field_val is None
        for field_val in (
            amount,
            currency,
            registered_date,
            share_count,
            capital_type,
            paid_in,
            fully_paid_in,
            bound,
        )
    ):
        return None

    return {
        "organisation_number": profile_org,
        "amount": amount,
        "currency": currency,
        "registered_date": registered_date,
        "share_count": share_count,
        "type": capital_type,
        "paid_in": paid_in,
        "fully_paid_in": fully_paid_in,
        "bound": bound,
        "source_url": reg_bulk_ev.get("source_url"),
        "source_type": reg_bulk_ev.get("source_type"),
        "source_class": reg_bulk_ev.get("source_class") or reg_bulk_ev.get("source_type"),
        "retrieved_at": reg_bulk_ev.get("retrieved_at"),
        "effective_at": reg_bulk_ev.get("effective_at") or reg_bulk_ev.get("as_of"),
        "content_sha256": reg_bulk_ev.get("content_sha256"),
    }


def emit_capital_metrics(profile: dict[str, Any]) -> dict[str, Any]:
    """Deterministically propagate retained BRREG share-capital and equity-registration metadata.

    Populates:
    - profile["capital"] (canonical structured dictionary or None)
    - profile["share_capital"]
    - profile["share_capital_currency"]
    - profile["share_count"]
    - profile["capital_registered_date"]
    - profile["capital_type"]

    Preserves profile["evidence"] unchanged.
    """
    record = extract_capital_record(profile)
    if record is None:
        profile["capital"] = None
        profile["share_capital"] = None
        profile["share_capital_currency"] = None
        profile["share_count"] = None
        profile["capital_registered_date"] = None
        profile["capital_type"] = None
        return profile

    profile["capital"] = record
    profile["share_capital"] = record["amount"]
    profile["share_capital_currency"] = record["currency"]
    profile["share_count"] = record["share_count"]
    profile["capital_registered_date"] = record["registered_date"]
    profile["capital_type"] = record["type"]
    return profile
