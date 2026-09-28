# Phase 19 — Emit Governance & Roles from Retained Evidence Report

## Executive Summary

Phase 19 successfully implemented the safe, zero-network-request propagation of already-retained official BRREG role and governance evidence into the competition profile and terminal envelope structures across the frozen 1,000-company corpus.

### Key Achievements
- **Zero Network Requests**: 0 HTTP requests emitted during emission; $0.00 third-party API cost.
- **4,019 Verified Role Records Emitted**: Surfaced all 4,019 retained BRREG role records directly into `profile["roles"]` and 6 structured top-level governance convenience fields across 1,000 companies (100% coverage).
- **100% Entity Anchoring**: Strict validation that every emitted role record matches the profile's exact organisation number, while preserving corporate role holders' own organisation numbers in `holder_organisation_number`.
- **Evidence Integrity Preserved**: Original `evidence["roles"]` dictionaries, source URLs, content hashes, and retrieval timestamps remain completely untouched.
- **Zero Fabrication / Missingness Discipline**: Missing role evidence or absent role categories strictly remain `None` (never converted to empty arrays `[]` or fabricated leadership claims).
- **All 7 Hard Qualification Gates Passed**: 1,000/1,000 valid terminal envelopes, 100% exact identity, 100% idempotent refresh replay, 0 wrong companies, 0 unsupported claims.

---

## 1. Schema Inspection & Design Decision

### Audit of Retained Role Evidence Structure
As established in Phase 17C, `profile["evidence"]["roles"]["value"]["roles"]` already retained structured governance records from the official Brønnøysundregistrene (`/api/enheter/{org}/roller`) API for all 1,000 companies (4,019 total role records). Prior to Phase 19, none of these role records were exposed at the top level of `profile`.

### Emitted Schema Location
To ensure maximum compatibility with automated evaluators, research queries, and schema validators:
1. **Canonical Structured List (`profile["roles"]`)**: Emits the complete, ordered list of entity-anchored role dictionaries. Each record preserves:
   - `organisation_number`: Anchored to the profile's company (`profile["organisation_number"]`)
   - `company_organisation_number`: Anchored to the profile's company
   - `holder_organisation_number`: Preserves corporate role holder's org number (e.g. auditing or accounting firm) or `None` for natural persons
   - `name`: Normalized string representation of the person or corporate holder name
   - `raw_name`: Exact original name structure from retained evidence
   - `role_code`: Official BRREG code (`LEDE`, `DAGL`, `MEDL`, `VARA`, `REVI`, `REGN`, etc.)
   - `role`: Official role title (`Styrets leder`, `Daglig leder`, `Styremedlem`, etc.)
   - `group_code` & `group`: Official BRREG role group metadata
   - `appointment_date` & `last_changed`: Preserved dates from registry
   - `inactive`: Boolean status flag
   - `source_url`, `source_type`, `retrieved_at`, `content_sha256`: Full provenance metadata
2. **Top-Level Convenience Fields**:
   - `profile["board_chair"]`: Primary active `LEDE` role dict (or `None`)
   - `profile["managing_director"]`: Primary active `DAGL` (CEO) role dict (or `None`)
   - `profile["board_members"]`: List of `MEDL` role dicts (or `None`)
   - `profile["deputy_board_members"]`: List of `VARA` role dicts (or `None`)
   - `profile["auditors"]`: List of `REVI` role dicts (or `None`)
   - `profile["authorized_accountants"]`: List of `REGN` role dicts (or `None`)
3. **Missingness Discipline**: When role evidence is absent, `not_found`, `source_error`, `not_fetched`, or when a specific role category is not present for a company, the corresponding field is set to `None` rather than an empty factual claim.

---

## 2. Implementation Details

A dedicated module was created at `src/norway_company_agent/roles_emission.py` with two core functions:
- `extract_role_record(...)`: Transforms a single retained role record into an entity-anchored dictionary with normalized name and provenance fields.
- `emit_roles_metrics(profile)`: Safely validates entity alignment and populates `profile["roles"]` and top-level governance convenience fields.

### Integration Points
- `src/norway_company_agent/__init__.py`: Exports `emit_roles_metrics` and `extract_role_record`.
- `scripts/run_competition_batch.py`:
  - Calls `emit_roles_metrics(profile)` inside `enrich(profile)` right after `emit_financial_metrics(profile)`.
  - Calls `emit_roles_metrics(emit_financial_metrics(state[org]))` when materializing `ordered_profiles` prior to terminal envelope creation and JSONL output.

---

## 3. Entity Safety & Integrity Guarantees

Every emitted role record is strictly guarded by deterministic safety checks:
1. **Organisation Number Matching**: If `source_row_key` is present on `evidence["roles"]`, it must equal `profile["organisation_number"]`.
2. **Source URL Verification**: If `source_url` contains `/enheter/{org}`, the extracted 9-digit organisation number must match `profile["organisation_number"]`.
3. **Record-Level Company Anchor Check**: If a raw role record explicitly specifies `company_organisation_number`, any mismatch against `profile["organisation_number"]` raises a `ValueError`.
4. **No Cross-Entity Leakage**: Any mismatch immediately raises a `ValueError`, preventing cross-company role contamination.
5. **No Overwrites**: The original `evidence["roles"]` dictionary is never modified.

---

## 4. Focused Test Suite (`tests/test_roles_emission.py`)

A comprehensive 14-test suite was created in `tests/test_roles_emission.py` covering every required scenario:
1. `test_complete_role_set`: Validates extraction of all 6 primary role categories (`DAGL`, `LEDE`, `MEDL`, `VARA`, `REVI`, `REGN`).
2. `test_ceo_dagl_emission`: Verifies `managing_director` emission, active role preference, and `None` when absent.
3. `test_board_chair_lede_emission`: Verifies `board_chair` emission and `None` when absent.
4. `test_board_members_medl_emission`: Verifies multiple `MEDL` board members and `None` when absent.
5. `test_auditor_revi_emission`: Verifies `REVI` statutory auditor emission with corporate holder org number preserved.
6. `test_accountant_regn_emission`: Verifies `REGN` authorized accountant emission with corporate list-name normalization.
7. `test_deputy_board_member_vara_emission`: Verifies `VARA` deputy board members emission and `None` when absent.
8. `test_appointment_change_date_preservation`: Confirms `last_changed` and `appointment_date` preservation.
9. `test_missing_role_evidence`: Confirms `not_found`, `source_error`, `not_fetched`, missing evidence, and empty lists leave all fields `None`.
10. `test_organisation_number_mismatch_rejection`: Confirms URL, `source_row_key`, and record org mismatches raise `ValueError`.
11. `test_source_metadata_preservation`: Validates `source_url`, `source_type`, `retrieved_at`, and `content_sha256` on every emitted record.
12. `test_deterministic_output`: Confirms repeatable, idempotent execution.
13. `test_original_evidence_unchanged`: Confirms `evidence["roles"]` is never mutated.
14. `test_zero_network_requests`: Patches `socket.socket` to prove zero network calls during emission.

**Test Result**: 14/14 tests passed in 0.003s.

---

## 5. 1,000-Company Corpus Rebuild & Validation

The full 1,000-company corpus was rebuilt using the production batch pipeline:
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

### Validation Audit Results
- **Profiles Emitted**: Exactly 1,000
- **Envelopes Emitted**: Exactly 1,000
- **Unique Organisation Numbers**: Exactly 1,000 / 1,000
- **Silent Drops**: 0
- **Terminal Envelope Validation**: **PASSED** (`validation.passed == True`, 0 invalid states)
- **Refresh Replay Validation**: **PASSED** (`precision: 1.0`, `recall: 1.0`, `idempotent_rerun: True`)
- **Official Identity Completeness**: **PASSED** (1,000 / 1,000 exact matches)
- **Wrong-Company Publications**: 0
- **Unsupported Claims**: 0

---

## 6. Measured Improvement & Coverage Comparison

| Metric / Role Category | Before Phase 19 | After Phase 19 | Change |
|---|---|---|---|
| **Companies with Role Evidence** | 1,000 | 1,000 | 0 (No new fetching) |
| **Companies with Top-Level `roles`** | 0 | 1,000 (100.0%) | **+1,000 companies** |
| **Total Role Records Emitted** | 0 | 4,019 | **+4,019 role records** |
| **- Board Chair (`LEDE` / `board_chair`)** | 0 | 986 companies (986 records) | **+986 companies (98.6%)** |
| **- Managing Director / CEO (`DAGL` / `managing_director`)** | 0 | 648 companies (650 records) | **+648 companies (64.8%)** |
| **- Board Members (`MEDL` / `board_members`)** | 0 | 490 companies (963 records) | **+490 companies / +963 records** |
| **- Authorized Accountants (`REGN` / `authorized_accountants`)** | 0 | 642 companies (683 records) | **+642 companies / +683 records** |
| **- Statutory Auditors (`REVI` / `auditors`)** | 0 | 342 companies (343 records) | **+342 companies / +343 records** |
| **- Deputy Board Members (`VARA` / `deputy_board_members`)** | 0 | 236 companies (309 records) | **+236 companies / +309 records** |
| **- Business Manager (`FFØR`)** | 0 | 49 companies (49 records) | **+49 records in `roles`** |
| **- Other Official Roles (`DTPR`, `HFOR`, `DTSO`, `KONT`, `INNH`, `REPR`, `BOBE`)** | 0 | 21 companies (36 records) | **+36 records in `roles`** |
| **Network Requests Emitted** | 0 | 0 | **0** |
| **Outbound Bandwidth** | 0 bytes | 0 bytes | **0 bytes** |
| **Third-Party API Cost** | $0.00 | $0.00 | **$0.00** |
| **Batch Runtime** | - | 27.8s | Pure in-memory transformation |
| **Local Proxy v3 Score** | 54.869 | 54.869 | Unchanged (proxy checks module presence only) |
| **Official 35-Pt Coverage Benefit** | Unsurfaced evidence | 4,019 verified role facts | **Substantial official gain** (unverified by local proxy) |

---

## 7. Regression Invariants

A full regression run across all phase test suites confirmed:
- `tests/test_roles_emission.py`: 14/14 passed
- `tests/test_financial_emission.py`: 9/9 passed
- `tests/test_official_workforce.py`: 5/5 passed
- `tests/test_ratings_reviews_audit.py`: 5/5 passed
- `tests/test_hiring_jobs_audit.py`: 6/6 passed
- `tests/test_freshness_and_breadth_audit.py`: 5/5 passed
- `tests/test_subunits.py`: 6/6 passed
- `tests/test_phase11_connectors.py`: 2/2 passed
- **Total Focused Suite**: 50 / 50 tests passed in 0.025s

### Confirmed Unchanged Invariants
- Website crawling & website identity decisions: unchanged
- Phase 18 financial values (997 companies, 9,651 facts) & financial evidence: unchanged
- Workforce observations (337 BRREG observations): unchanged
- Social observations (43 verified handles): unchanged
- News observations (16 website posts): unchanged
- External-footprint observations: unchanged
- Terminal states & organisation-number membership (1,000 exact companies): unchanged

---

## 8. Artifacts Created / Updated
- Module: `src/norway_company_agent/roles_emission.py`
- Package Exports: `src/norway_company_agent/__init__.py`
- Batch Pipeline: `scripts/run_competition_batch.py`
- Test Suite: `tests/test_roles_emission.py`
- Audit JSON: `out/phase19-roles-emission-report.json`
- Full Report: `out/phase19-roles-emission-report.md`
- Updated Profiles: `out/profiles.jsonl`
- Updated Envelopes: `out/envelopes.jsonl`
- Updated Run Report: `out/run-report.json`
- Competition v3 Score: `out/phase19-competition-v3-score.json`
