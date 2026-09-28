# Phase 23 — Emit Statutory Purpose, Operational Activity, VAT/MVA & Audit Metadata

## 1. Implementation Summary

Phase 23 completes the planned official Brønnøysundregistrene (BRREG) evidence-propagation sequence by exposing the remaining high-value retained BRREG fields identified in the Phase 20 audit across the frozen 1,000-company corpus (`out/profiles.jsonl` and `out/envelopes.jsonl`):

- **Module created**: `src/norway_company_agent/purpose_vat_audit_emission.py`
  - `extract_purpose_activity_record(profile)`
  - `extract_vat_record(profile)`
  - `extract_audit_record(profile)`
  - `emit_purpose_vat_audit_metrics(profile)`
- **Pipeline integration**: `src/norway_company_agent/__init__.py` and `scripts/run_competition_batch.py`
- **Unit test suite**: `tests/test_purpose_vat_audit_emission.py` (`6 / 6` passed; `70 / 70` passed across all 11 phase regression suites)
- **Operations & Cost**: **0 network requests**, **0 outbound bytes**, **\$0.00 external API cost**, **28.00s** deterministic `--resume` rebuild.

---

## 2. Exact Coverage Before vs. After Phase 23

| Category / Emitted Field | Structured Path | Top-Level Convenience Field | Source Key (`evidence.registry.value`) | Before | After | Coverage % | Missing / Excluded | Emitted Facts |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Statutory purpose** | `purpose_activity.statutory_purpose` | `statutory_purpose` | `vedtektsfestetFormaal` (col 64) | 0 | **963** | 96.3% | 37 (`34` absent + `3` shifted) | **963** |
| **Operational activity** | `purpose_activity.operational_activity` | `operational_activity` | `aktivitet` (col 65) | 0 | **997** | 99.7% | 3 (`3` shifted) | **997** |
| **MVA registered status** | `vat.registered` | `vat_registered` | `registrertIMvaRegisteret` (col 39) | 0 | **1,000** | 100.0% | 0 | **1,000** (`507` `True`, `493` `False`) |
| **MVA registration date** | `vat.registered_date` | `vat_registered_date` | `registreringsdatoMerverdiavgiftsregisteret` (col 40) | 0 | **507** | 50.7% | 493 | **507** |
| **MVA Enhetsregisteret date** | `vat.enhetsregisteret_registered_date` | `vat_enhetsregisteret_registered_date` | `registreringsdatoMerverdiavgiftsregisteretEnhetsregisteret` (col 41) | 0 | **507** | 50.7% | 493 | **507** |
| **Voluntary MVA descriptions** | `vat.voluntary_descriptions` | `vat_voluntary_descriptions` | `frivilligMvaRegistrertBeskrivelser` (col 42) | 0 | **94** | 9.4% | 906 | **94** |
| **Voluntary MVA date** | `vat.voluntary_registered_date` | `vat_voluntary_registered_date` | `registreringsdatoFrivilligMerverdiavgiftsregisteret` (col 43) | 0 | **94** | 9.4% | 906 | **94** |
| **Audit exemption date** | `audit.exemption_date` | `audit_exemption_date` | `fravalgRevisjonDato` (col 69) | 0 | **636** | 63.6% | 364 (`361` absent + `3` shifted) | **636** |
| **Audit decision date** | `audit.decision_date` | `audit_decision_date` | `fravalgRevisjonBeslutningsDato` (col 70) | 0 | **436** | 43.6% | 564 (`561` absent + `3` shifted) | **436** |
| **Total Phase 23 Facts** | `purpose_activity`, `vat`, `audit` | 9 convenience fields | `evidence.registry.value` | **0** | **1,000 companies** | **100.0%** | **—** | **5,234 verified facts** |

---

## 3. CSV-Shift Protection & Data-Quality Findings

1. **CSV-Shifted Rows Excluded (`3` companies: `998600421`, `914882036`, `926768026`)**:
   - Unescaped quotes and commas in `vedtektsfestetFormaal` (col 64) and `aktivitet` (col 65) corrupt columns $\ge 64$ on `998600421` (`PRISMA CONSULT AS`), `914882036` (`KULTURLANDRO AS`), and `926768026` (`THREE SOULS AS`).
   - `is_csv_quote_shifted` and `get_safe_bulk_field` block `purpose_activity` (`statutory_purpose`, `operational_activity`) and `audit` (`exemption_date`, `decision_date`) on all 3 rows (`0` shifted values emitted).
   - Because MVA columns (`cols 39–43`) reside $>20$ columns before column 64, they are unshifted across all `1,000` companies and pass strict boolean/date/description validation.
2. **Audit Exemption Schema in BRREG**:
   - BRREG's bulk `enheter` schema contains explicit date columns `fravalgRevisjonDato` (`636` clean companies) and `fravalgRevisjonBeslutningsDato` (`436` clean companies, all of which are a strict subset of the `636`), and does not contain a separate boolean `fravalgRevisjon` column. In compliance with strict non-inference rules, only the explicit dates are emitted and no boolean status is inferred from dates, legal form, or auditor roles.
3. **Voluntary MVA Consistency**:
   - All `94` companies with `frivilligMvaRegistrertBeskrivelser` (`"Utleier av bygg eller anlegg"`) are the exact same `94` companies with `registreringsdatoFrivilligMerverdiavgiftsregisteret`, and all `94` have `registrertIMvaRegisteret == "true"`.

---

## 4. Regression, Validation & Scoring Summary

- **Phase 18 Financials**: `997 / 1,000` companies, `9,651` facts (`UNCHANGED`)
- **Phase 19 Roles**: `1,000 / 1,000` companies, `4,019` role records (`UNCHANGED`)
- **Phase 21 Addresses, Contact & Registration Dates**: `business_address=998`, `postal_address=246`, `official_email=242`, `official_phone=182`, `official_mobile=182`, `registration_date=1000`, `foundation_date=991`, `articles_date=967`, `foretaksregisteret_date=974`, `foretaksregisteret_registered=1000` (`UNCHANGED`)
- **Phase 22 Share Capital**: `938 / 1,000` companies, `4,671` core facts, `4,698` total facts (`UNCHANGED`)
- **Workforce, Website, Social Handles, Activity/News & External Observations**: `UNCHANGED`
- **Wrong-Company External Publications**: `0`
- **Unsupported External Claims**: `0`
- **Terminal Envelope Validation**: `PASS` (`1,000` profiles, `1,000` envelopes, `0` silent drops, `0` duplicates)
- **Refresh Replay (`out/refresh-test.json`)**: `PASS` (`precision=1.0`, `recall=1.0`, `idempotent_rerun=true`)
- **Deterministic Idempotent Replay**: `PASS`
- **Local Competition Proxy v3 Score (`out/phase23-competition-v3-score.json`)**: **`56.869 / 100.0` before $\rightarrow$ `56.869 / 100.0` after (`local score unchanged`)**, all 7 qualification gates `PASS`.
- **Decision**: **ACCEPT Phase 23**.

---

## 5. Final Readiness Assessment

1. **What is complete**:
   - Full 1,000-company official BRREG + website + subunit + external footprint corpus (`out/profiles.jsonl` and `out/envelopes.jsonl`) with all terminal state invariants and qualification gates passing.
   - Complete zero-network top-level emission of official BRREG evidence across **Phases 18, 19, 21, 22, and 23**:
     - Phase 18 financials (`997` companies, `9,651` facts)
     - Phase 19 governance & roles (`1,000` companies, `4,019` role records)
     - Phase 21 structured business/postal addresses, official contact channels, and registration dates (`1,000` companies, `14,222` structured component and scalar facts)
     - Phase 22 share capital & equity registration metadata (`938` companies, `4,698` facts)
     - Phase 23 statutory purpose, operational activity, MVA/VAT, and audit exemption metadata (`1,000` companies, `5,234` facts)
2. **What remains before submission**:
   - No further official BRREG evidence-propagation phases are required; virtually all high-coverage, high-signal BRREG evidence (`>37,800` top-level structured facts across Phases 18–23) is now explicitly surfaced at top level and inside `envelopes.jsonl`.
   - Final packaging verification (confirming git status, manifest files, and submission email metadata).
3. **Any remaining risks**:
   - In `tests/test_poc.py`, 3 legacy unit tests written for the pre-Phase-12 name-only website/social identity gate fail because Phase 12 intentionally tightened identity gates to require exact organisation-number anchoring (`0` wrong-company tolerance). The production identity gates must NOT be loosened.
4. **Whether another implementation phase is justified**:
   - **No additional BRREG emission phase is justified.** Remaining un-emitted BRREG bulk fields (`erIKonsern`, secondary NACE codes `naeringskode2/3`) are either low-coverage (`8.9%` for NACE 2, `0.6%` for NACE 3) or low-value boolean flags. External connector expansion (ratings/jobs/sentiment) should only be pursued if a compliant, explicitly licensed API source with exact organisation-number matching is available.
5. **Recommended final competition command**:
   ```bash
   uv run python scripts/run_competition_batch.py \
     --organisations entry-companies.jsonl \
     --bulk brreg-enheter.csv \
     --subunits-bulk brreg-underenheter.csv \
     --profiles-output out/profiles.jsonl \
     --output out/envelopes.jsonl \
     --report out/run-report.json \
     --run-id local-001 \
     --expected-count 1000 \
     --resume
   ```
6. **Repository / submission cleanup requirements**:
   - Keep `entry-companies.jsonl`, `out/profiles.jsonl`, `out/envelopes.jsonl`, `out/run-report.json`, `out/refresh-test.json`, and phase audit/emission reports intact.
   - Do not commit temporary `.tmp` files or unverified experimental outputs.
