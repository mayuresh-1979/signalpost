"""Norway company enrichment POC."""
from .capital_emission import emit_capital_metrics, extract_capital_record
from .contact_registration_emission import (
    emit_contact_registration_metrics,
    extract_business_address,
    extract_contact_channels,
    extract_postal_address,
    extract_registration_dates,
    get_safe_bulk_field,
    is_csv_quote_shifted,
)
from .financial_emission import emit_financial_metrics, extract_financial_record
from .purpose_vat_audit_emission import (
    emit_purpose_vat_audit_metrics,
    extract_audit_record,
    extract_purpose_activity_record,
    extract_vat_record,
)
from .roles_emission import emit_roles_metrics, extract_role_record

__all__ = [
    "emit_capital_metrics",
    "emit_contact_registration_metrics",
    "emit_financial_metrics",
    "emit_purpose_vat_audit_metrics",
    "emit_roles_metrics",
    "extract_audit_record",
    "extract_business_address",
    "extract_capital_record",
    "extract_contact_channels",
    "extract_financial_record",
    "extract_postal_address",
    "extract_purpose_activity_record",
    "extract_registration_dates",
    "extract_role_record",
    "extract_vat_record",
    "get_safe_bulk_field",
    "is_csv_quote_shifted",
]
