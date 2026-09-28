# Phase 21 — Emit Structured Addresses, Official Contact Channels & Core Registration Dates

## 1. Executive Summary

Phase 21 propagates the 10 highest-priority retained official Brønnøysundregistrene (BRREG) fields identified in the Phase 20 audit into explicit top-level profile fields across the frozen 1,000-company Signalpost corpus (`out/profiles.jsonl` and `out/envelopes.jsonl`):

1. `profile["business_address"]` (`998 / 1,000` companies, `6,973` structured component facts)
2. `profile["postal_address"]` (`246 / 1,000` companies, `1,709` structured component facts; covers the remaining 2 companies without a registered business address for **1,000 / 1,000 (100.0%)** official address coverage)
3. `profile["official_email"]` (`242 / 1,000` companies)
4. `profile["official_phone"]` (`182 / 1,000` companies)
5. `profile["official_mobile"]` (`182 / 1,000` companies; `315 / 1,000` companies have phone or mobile, and `357 / 1,000` have at least one official contact channel)
6. `profile["registration_date"]` (`1,000 / 1,000` companies)
7. `profile["foundation_date"]` (`991 / 1,000` companies)
8. `profile["articles_date"]` (`967 / 1,000` companies)
9. `profile["foretaksregisteret_date"]` (`974 / 1,000` companies)
10. `profile["foretaksregisteret_registered"]` (`1,000 / 1,000` companies: `974` `True`, `26` `False`)

All propagation ran in deterministic `--resume` mode with **0 network requests**, **0 outbound bytes**, and **\$0.00 external API cost**.

---

## 2. Coverage Summary (Before vs. After Phase 21)

| Top-Level Emitted Field | Source Evidence Path | Companies Before | Companies After | Coverage % | Missing | Structured / Scalar Facts Emitted |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `business_address` | `evidence.registry_live.value.business_address` | 0 | **998** | 99.8% | 2 | **6,973** components (`998` dicts) |
| `postal_address` | `evidence.registry_live.value.postal_address` | 0 | **246** | 24.6% | 754 | **1,709** components (`246` dicts) |
| `official_email` | `evidence.registry.value.epostadresse` | 0 | **242** | 24.2% | 758 | **242** |
| `official_phone` | `evidence.registry.value.telefon` | 0 | **182** | 18.2% | 818 | **182** |
| `official_mobile` | `evidence.registry.value.mobil` | 0 | **182** | 18.2% | 818 | **182** |
| `registration_date` | `evidence.registry.value.registreringsdatoenhetsregisteret` | 0 | **1,000** | 100.0% | 0 | **1,000** |
| `foundation_date` | `evidence.registry.value.stiftelsesdato` | 0 | **991** | 99.1% | 9 | **991** |
| `articles_date` | `evidence.registry.value.vedtektsdato` | 0 | **967** | 96.7% | 33 | **967** |
| `foretaksregisteret_date` | `evidence.registry.value.registreringsdatoForetaksregisteret` | 0 | **974** | 97.4% | 26 | **974** |
| `foretaksregisteret_registered` | `evidence.registry.value.registrertIForetaksregisteret` | 0 | **1,000** | 100.0% | 0 | **1,000** (`974` `True`, `26` `False`) |
| **Total** | **Official BRREG Retained Evidence** | **0** | **1,000** | **100.0%** | **—** | **6,782 top-level values / 14,222 component & scalar facts** |

### Structured Address Component Breakdown

| Component Key | `business_address` (`998` companies) | `postal_address` (`246` companies) |
| :--- | :---: | :---: |
| `adresse` | 991 | 245 |
| `postnummer` | 996 | 242 |
| `poststed` | 998 | 246 |
| `kommune` | 996 | 242 |
| `kommunenummer` | 996 | 242 |
| `land` | 998 | 246 |
| `landkode` | 998 | 246 |
| **Total Component Facts** | **6,973** | **1,709** |

Each emitted `business_address` and `postal_address` dictionary also retains official BRREG provenance metadata (`organisation_number`, `source_url`, `source_type`, `retrieved_at`, `content_sha256`). When `postal_address` is absent in `evidence.registry_live.value`, `profile["postal_address"]` is strictly `None` (never copied from `business_address`).

---

## 3. CSV Quote-Shift Protection Verification

In `brreg-enheter.csv`, 3 companies (`998600421`, `914882036`, `926768026`) contain unescaped double-quotes and commas inside column 64 (`vedtektsfestetFormaal`) or column 65 (`aktivitet`), shifting columns $\ge 64$ rightward in `evidence.registry.value`.

- `is_csv_quote_shifted(registry_value)` in `src/norway_company_agent/contact_registration_emission.py` detects all 3 affected rows (`998600421`, `914882036`, `926768026`).
- `get_safe_bulk_field(registry_value, field)` explicitly blocks any access to columns $\ge 64$ (`SHIFTED_BULK_COLUMNS_FROM_64`) on shifted rows, returning `None`.
- All Phase 21 bulk fields (`epostadresse` col 17, `telefon` col 18, `mobil` col 19, `registreringsdatoenhetsregisteret` col 37, `stiftelsesdato` col 38, `registrertIForetaksregisteret` col 46, `registreringsdatoForetaksregisteret` col 47, `vedtektsdato` col 63) reside strictly prior to column 64 and are validated by strict format checks (`_validate_iso_date`, `_validate_boolean`, `_validate_email`, `_validate_phone`), while `business_address` and `postal_address` are sourced from clean JSON in `evidence.registry_live.value`.
- **Result**: `0` corrupted or shifted values emitted across all 1,000 companies.

---

## 4. Validation, Determinism & Scoring Summary

- **Network Requests**: `0` (`profiles_fetched_this_run = 0`, `resumed_profiles = 1000`)
- **External API Cost**: `\$0.00`
- **Terminal Envelope Validation**: `passed = true` (`1,000` profiles, `1,000` envelopes, `0` silent drops, `0` duplicate organisation numbers, all entity and module states terminal)
- **Deterministic Idempotent Replay**: Verified across all `1,000` profiles
- **Refresh Replay (`out/refresh-test.json`)**: `qualification_passed = true`, `precision = 1.0`, `recall = 1.0`, `idempotent_rerun = true`
- **Local Competition Proxy v3 Score (`out/phase21-competition-v3-score.json`)**:
  - With `--resume-report`: **`56.869 / 100.0`** (`qualification_passed = true`, all 7 qualification gates green)
  - Without `--resume-report`: **`54.869 / 100.0`** (`qualification_passed = true`)
  - *Note*: The local proxy v3 scorer awards `4.0 / 4.0` to `official_identity` based on `evidence.registry_live` organisation number match, so top-level address/contact/registration fields do not alter the local proxy formula. They directly expand structured top-level coverage for the official 35-point Signalpost Information Coverage evaluation.

---

## 5. Regression & Test Suite Verification

- **Phase 18 Financials Preserved**: `997 / 1,000` companies with top-level `financials` (`9,651` facts) unchanged.
- **Phase 19 Governance & Roles Preserved**: `1,000 / 1,000` companies with top-level `roles` (`4,019` role records) unchanged.
- **Workforce, Website & External Observations Preserved**: Unchanged.
- **Phase 20 Audit Artifacts Preserved**: `out/phase20-brreg-coverage-audit.json` and `out/phase20-brreg-coverage-report.md` untouched.
- **Phase 21 Unit Tests (`tests/test_contact_registration_emission.py`)**: `7 / 7` passed (`57 / 57` passed across all phase test suites).
