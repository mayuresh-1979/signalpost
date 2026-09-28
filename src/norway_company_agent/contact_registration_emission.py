from __future__ import annotations

import re
from datetime import date
from typing import Any

ADDRESS_COMPONENT_KEYS = (
    "adresse",
    "postnummer",
    "poststed",
    "kommune",
    "kommunenummer",
    "land",
    "landkode",
)

# Columns at index >= 64 in brreg-enheter.csv (starting at vedtektsfestetFormaal).
# In rows with unescaped quotes + commas inside vedtektsfestetFormaal or aktivitet,
# all columns from index 64 onward shift right and must not be trusted.
SHIFTED_BULK_COLUMNS_FROM_64 = frozenset(
    {
        "vedtektsfestetFormaal",
        "aktivitet",
        "paategninger",
        "underUtenlandskInsolvensbehandlingDato",
        "underRekonstruksjonsforhandlingDato",
        "fravalgRevisjonDato",
        "fravalgRevisjonBeslutningsDato",
        "erIKonsern",
        "kapital.belop",
        "kapital.antallAksjer",
        "kapital.type",
        "kapital.bundet",
        "kapital.valuta",
        "kapital.innbetalt",
        "kapital.fulltInnbetalt",
        "kapital.innfortDato",
        "registreringsnummerIHjemlandet",
        "utenlandskRegisterNavn",
        "utenlandskRegisterAdresse.land",
        "utenlandskRegisterAdresse.poststed",
        "utenlandskRegisterAdresse.adresse",
        "underlagtLovgivningLand",
        "underlagtLovgivningLandKode",
        "foretaksformIHjemlandet.kode",
        "foretaksformIHjemlandet.beskrivelse",
        "foretaksformIHjemlandet.beskrivelseBokmaal",
    }
)

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PHONE_RE = re.compile(r"^[\d\s+\-().]+$")


def is_csv_quote_shifted(registry_value: dict[str, Any] | None) -> bool:
    """Detect the Phase 20 CSV quote-shift corruption signature on bulk registry rows."""
    if not isinstance(registry_value, dict):
        return False
    if "null" in registry_value or None in registry_value:
        return True
    paategninger = str(registry_value.get("paategninger") or "").strip().lower()
    if paategninger and paategninger not in {"true", "false"}:
        return True
    er_i_konsern = str(registry_value.get("erIKonsern") or "").strip().lower()
    if er_i_konsern and er_i_konsern not in {"true", "false"}:
        return True
    return False


def get_safe_bulk_field(registry_value: dict[str, Any] | None, field: str) -> Any:
    """Retrieve a field from evidence.registry.value while blocking >=64 columns on quote-shifted rows."""
    if not isinstance(registry_value, dict):
        return None
    if field in SHIFTED_BULK_COLUMNS_FROM_64 and is_csv_quote_shifted(registry_value):
        return None
    return registry_value.get(field)


def _validate_iso_date(value: Any) -> str | None:
    """Validate that value is a strict YYYY-MM-DD calendar date."""
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
    """Validate a boolean or 'true'/'false' string without inferring from dates."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned == "true":
            return True
        if cleaned == "false":
            return False
    return None


def _validate_email(value: Any) -> str | None:
    """Validate that a retained official email is a real email string without normalizing or inventing."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or cleaned.lower().startswith("mailto:"):
        return None
    if "@" not in cleaned:
        return None
    local_part, _, domain_part = cleaned.partition("@")
    if not local_part.strip() or "." not in domain_part or not domain_part.strip("."):
        return None
    return cleaned


def _validate_phone(value: Any) -> str | None:
    """Validate that a retained phone/mobile value contains valid telephone characters and digits."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or cleaned.lower().startswith("tel:"):
        return None
    if _ISO_DATE_RE.match(cleaned):
        return None
    if not _PHONE_RE.match(cleaned):
        return None
    digit_count = sum(ch.isdigit() for ch in cleaned)
    if digit_count < 3:
        return None
    return cleaned


def _verify_registry_live_entity(profile_org: str, reg_live_ev: dict[str, Any]) -> dict[str, Any] | None:
    """Verify entity anchoring on evidence.registry_live and return its value dict if available."""
    if not isinstance(reg_live_ev, dict) or reg_live_ev.get("status") != "available":
        return None

    source_row_key = reg_live_ev.get("source_row_key")
    if source_row_key and str(source_row_key).strip() != profile_org:
        raise ValueError(
            f"registry_live entity mismatch: source_row_key {source_row_key!r} "
            f"!= profile organisation_number {profile_org!r}"
        )

    source_url = reg_live_ev.get("source_url")
    if source_url:
        match = re.search(r"/enheter/(\d{9})\b", str(source_url))
        if match and match.group(1) != profile_org:
            raise ValueError(
                f"registry_live entity mismatch: source_url org {match.group(1)!r} "
                f"!= profile organisation_number {profile_org!r}"
            )

    val = reg_live_ev.get("value")
    if not isinstance(val, dict):
        return None

    val_org = val.get("organisation_number") or val.get("organisasjonsnummer")
    if val_org is not None and str(val_org).strip() != profile_org:
        raise ValueError(
            f"registry_live entity mismatch: value organisation_number {val_org!r} "
            f"!= profile organisation_number {profile_org!r}"
        )

    return val


def _verify_registry_bulk_entity(profile_org: str, reg_bulk_ev: dict[str, Any]) -> dict[str, Any] | None:
    """Verify entity anchoring on evidence.registry and return its value dict if available."""
    if not isinstance(reg_bulk_ev, dict) or reg_bulk_ev.get("status") != "available":
        return None

    source_row_key = reg_bulk_ev.get("source_row_key")
    if source_row_key and str(source_row_key).strip() != profile_org:
        raise ValueError(
            f"registry bulk entity mismatch: source_row_key {source_row_key!r} "
            f"!= profile organisation_number {profile_org!r}"
        )

    val = reg_bulk_ev.get("value")
    if not isinstance(val, dict):
        return None

    val_org = val.get("organisasjonsnummer") or val.get("organisation_number")
    if val_org is not None and str(val_org).strip() != profile_org:
        raise ValueError(
            f"registry bulk entity mismatch: value organisasjonsnummer {val_org!r} "
            f"!= profile organisation_number {profile_org!r}"
        )

    return val


def _extract_structured_address(
    raw_addr: Any,
    profile_org: str,
    reg_live_ev: dict[str, Any],
) -> dict[str, Any] | None:
    """Extract only present, non-empty components from a registry_live address dictionary."""
    if not isinstance(raw_addr, dict):
        return None

    extracted: dict[str, Any] = {}
    for key in ADDRESS_COMPONENT_KEYS:
        if key not in raw_addr:
            continue
        val = raw_addr[key]
        if val is None or val == "" or val == []:
            continue
        if isinstance(val, list):
            cleaned_list = [str(item).strip() for item in val if str(item).strip()]
            if not cleaned_list:
                continue
            extracted[key] = cleaned_list
        elif isinstance(val, str):
            cleaned_str = val.strip()
            if not cleaned_str:
                continue
            extracted[key] = cleaned_str
        else:
            extracted[key] = val

    if not extracted:
        return None

    extracted["organisation_number"] = profile_org
    extracted["source_url"] = reg_live_ev.get("source_url")
    extracted["source_type"] = reg_live_ev.get("source_type")
    extracted["retrieved_at"] = reg_live_ev.get("retrieved_at")
    extracted["content_sha256"] = reg_live_ev.get("content_sha256")
    return extracted


def extract_business_address(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Extract structured registered business address from evidence.registry_live.value.business_address."""
    profile_org = str(profile.get("organisation_number") or "").strip()
    if not profile_org:
        raise ValueError("Profile is missing organisation_number")

    reg_live_ev = (profile.get("evidence") or {}).get("registry_live") or {}
    val = _verify_registry_live_entity(profile_org, reg_live_ev)
    if val is None:
        return None

    return _extract_structured_address(val.get("business_address"), profile_org, reg_live_ev)


def extract_postal_address(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Extract structured postal address from evidence.registry_live.value.postal_address.

    Never copies business_address into postal_address when postal_address is missing.
    """
    profile_org = str(profile.get("organisation_number") or "").strip()
    if not profile_org:
        raise ValueError("Profile is missing organisation_number")

    reg_live_ev = (profile.get("evidence") or {}).get("registry_live") or {}
    val = _verify_registry_live_entity(profile_org, reg_live_ev)
    if val is None:
        return None

    return _extract_structured_address(val.get("postal_address"), profile_org, reg_live_ev)


def extract_contact_channels(profile: dict[str, Any]) -> dict[str, Any]:
    """Extract official registered email, phone, and mobile from evidence.registry.value."""
    profile_org = str(profile.get("organisation_number") or "").strip()
    if not profile_org:
        raise ValueError("Profile is missing organisation_number")

    reg_bulk_ev = (profile.get("evidence") or {}).get("registry") or {}
    val = _verify_registry_bulk_entity(profile_org, reg_bulk_ev)
    if val is None:
        return {
            "official_email": None,
            "official_phone": None,
            "official_mobile": None,
        }

    return {
        "official_email": _validate_email(get_safe_bulk_field(val, "epostadresse")),
        "official_phone": _validate_phone(get_safe_bulk_field(val, "telefon")),
        "official_mobile": _validate_phone(get_safe_bulk_field(val, "mobil")),
    }


def extract_registration_dates(profile: dict[str, Any]) -> dict[str, Any]:
    """Extract core registration dates and Foretaksregisteret boolean status from evidence.registry.value."""
    profile_org = str(profile.get("organisation_number") or "").strip()
    if not profile_org:
        raise ValueError("Profile is missing organisation_number")

    reg_bulk_ev = (profile.get("evidence") or {}).get("registry") or {}
    val = _verify_registry_bulk_entity(profile_org, reg_bulk_ev)
    if val is None:
        return {
            "registration_date": None,
            "foundation_date": None,
            "articles_date": None,
            "foretaksregisteret_date": None,
            "foretaksregisteret_registered": None,
        }

    return {
        "registration_date": _validate_iso_date(
            get_safe_bulk_field(val, "registreringsdatoenhetsregisteret")
        ),
        "foundation_date": _validate_iso_date(
            get_safe_bulk_field(val, "stiftelsesdato")
        ),
        "articles_date": _validate_iso_date(
            get_safe_bulk_field(val, "vedtektsdato")
        ),
        "foretaksregisteret_date": _validate_iso_date(
            get_safe_bulk_field(val, "registreringsdatoForetaksregisteret")
        ),
        "foretaksregisteret_registered": _validate_boolean(
            get_safe_bulk_field(val, "registrertIForetaksregisteret")
        ),
    }


def emit_contact_registration_metrics(profile: dict[str, Any]) -> dict[str, Any]:
    """Deterministically propagate retained BRREG addresses, contact channels, and registration dates into profile."""
    profile_org = str(profile.get("organisation_number") or "").strip()
    if not profile_org:
        raise ValueError("Profile is missing organisation_number")

    profile["business_address"] = extract_business_address(profile)
    profile["postal_address"] = extract_postal_address(profile)

    contacts = extract_contact_channels(profile)
    profile["official_email"] = contacts["official_email"]
    profile["official_phone"] = contacts["official_phone"]
    profile["official_mobile"] = contacts["official_mobile"]

    dates = extract_registration_dates(profile)
    profile["registration_date"] = dates["registration_date"]
    profile["foundation_date"] = dates["foundation_date"]
    profile["articles_date"] = dates["articles_date"]
    profile["foretaksregisteret_date"] = dates["foretaksregisteret_date"]
    profile["foretaksregisteret_registered"] = dates["foretaksregisteret_registered"]

    return profile
